"""Dataset demo: generación en Python y persistencia solo en PostgreSQL."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_SCHEMA_HINT_FILE = (PROJECT_ROOT / "schema_hint_demo.txt").as_posix()
DEMO_BASE_TABLES = (
    "service_appointments",
    "insurance_policies",
    "services",
    "sales",
    "vehicles",
    "customers",
)
DEMO_MATERIALIZED_TABLES = ("mv_customer_lifecycle", "mv_sales_monthly")
DEMO_TABLES = (*DEMO_MATERIALIZED_TABLES, *DEMO_BASE_TABLES)

POSTGRES_DROP_ORDER = [
    "service_appointments",
    "insurance_policies",
    "services",
    "sales",
    "vehicles",
    "customers",
    "mv_sales_monthly",
    "mv_customer_lifecycle",
]

POSTGRES_DDL = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    customer_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    gender TEXT NOT NULL,
    age INTEGER NOT NULL,
    birth_date DATE NOT NULL,
    email TEXT,
    phone TEXT,
    city TEXT,
    state TEXT,
    segment TEXT NOT NULL,
    monthly_income DOUBLE PRECISION NOT NULL,
    risk_profile TEXT NOT NULL,
    created_at DATE NOT NULL
);

CREATE TABLE vehicles (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    vin TEXT NOT NULL UNIQUE,
    plate TEXT NOT NULL UNIQUE,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    year INTEGER NOT NULL,
    fuel_type TEXT NOT NULL,
    mileage INTEGER NOT NULL,
    created_at DATE NOT NULL
);

CREATE TABLE sales (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    sale_date DATE NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    channel TEXT NOT NULL,
    seller TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE services (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    service_date DATE NOT NULL,
    service_type TEXT NOT NULL,
    cost DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    workshop TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE insurance_policies (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    policy_start_date DATE NOT NULL,
    policy_end_date DATE NOT NULL,
    insurer TEXT NOT NULL,
    coverage_type TEXT NOT NULL,
    annual_premium DOUBLE PRECISION NOT NULL,
    policy_status TEXT NOT NULL,
    claim_count INTEGER NOT NULL,
    last_claim_date DATE
);

CREATE TABLE service_appointments (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    appointment_date DATE NOT NULL,
    service_type TEXT NOT NULL,
    appointment_status TEXT NOT NULL,
    workshop TEXT NOT NULL,
    cancellation_reason TEXT,
    attended INTEGER NOT NULL DEFAULT 0,
    created_at DATE NOT NULL,
    updated_at DATE NOT NULL
);

CREATE TABLE mv_sales_monthly (
    year_month TEXT NOT NULL,
    state TEXT NOT NULL,
    channel TEXT NOT NULL,
    segment TEXT NOT NULL,
    total_sales DOUBLE PRECISION NOT NULL,
    sales_count INTEGER NOT NULL,
    PRIMARY KEY (year_month, state, channel, segment)
);

CREATE TABLE mv_customer_lifecycle (
    customer_id INTEGER PRIMARY KEY REFERENCES customers(id),
    purchases INTEGER NOT NULL,
    total_amount DOUBLE PRECISION NOT NULL,
    first_sale_date DATE,
    last_sale_date DATE,
    avg_repurchase_days DOUBLE PRECISION
);

CREATE INDEX idx_customers_state ON customers(state);
CREATE INDEX idx_customers_age ON customers(age);
CREATE INDEX idx_customers_gender ON customers(gender);
CREATE INDEX idx_customers_segment ON customers(segment);
CREATE INDEX idx_vehicles_customer ON vehicles(customer_id);
CREATE INDEX idx_vehicles_unit_type ON vehicles(unit_type);
CREATE INDEX idx_sales_customer ON sales(customer_id);
CREATE INDEX idx_sales_vehicle ON sales(vehicle_id);
CREATE INDEX idx_sales_date ON sales(sale_date);
CREATE INDEX idx_sales_status ON sales(status);
CREATE INDEX idx_sales_state_date ON sales(customer_id, sale_date);
CREATE INDEX idx_services_customer ON services(customer_id);
CREATE INDEX idx_services_vehicle ON services(vehicle_id);
CREATE INDEX idx_services_date ON services(service_date);
CREATE INDEX idx_appointments_customer ON service_appointments(customer_id);
CREATE INDEX idx_appointments_vehicle ON service_appointments(vehicle_id);
CREATE INDEX idx_appointments_date ON service_appointments(appointment_date);
CREATE INDEX idx_appointments_status ON service_appointments(appointment_status);
CREATE INDEX idx_policies_customer ON insurance_policies(customer_id);
CREATE INDEX idx_policies_vehicle ON insurance_policies(vehicle_id);
CREATE INDEX idx_policies_status ON insurance_policies(policy_status);
CREATE INDEX idx_policies_end_date ON insurance_policies(policy_end_date);
CREATE INDEX idx_mv_sales_monthly_period ON mv_sales_monthly(year_month);
CREATE INDEX idx_mv_sales_monthly_state ON mv_sales_monthly(state);
CREATE INDEX idx_mv_customer_lifecycle_avg ON mv_customer_lifecycle(avg_repurchase_days);
"""

REFRESH_MATERIALIZED_DEMO_SQL = """
DELETE FROM mv_sales_monthly;
DELETE FROM mv_customer_lifecycle;
INSERT INTO mv_sales_monthly (year_month, state, channel, segment, total_sales, sales_count)
SELECT
    to_char(s.sale_date, 'YYYY-MM'),
    COALESCE(c.state, 'SIN_DATO'),
    COALESCE(s.channel, 'SIN_DATO'),
    COALESCE(c.segment, 'SIN_DATO'),
    ROUND(SUM(s.amount)::numeric, 2)::double precision,
    COUNT(*)::integer
FROM sales s
JOIN customers c ON c.id = s.customer_id
WHERE s.sale_date IS NOT NULL
GROUP BY 1, 2, 3, 4;
INSERT INTO mv_customer_lifecycle (
    customer_id,
    purchases,
    total_amount,
    first_sale_date,
    last_sale_date,
    avg_repurchase_days
)
WITH sale_gaps AS (
    SELECT
        s.customer_id,
        s.sale_date,
        s.amount,
        (s.sale_date - LAG(s.sale_date) OVER (PARTITION BY s.customer_id ORDER BY s.sale_date))::integer AS gap_days
    FROM sales s
    WHERE s.sale_date IS NOT NULL
)
SELECT
    customer_id,
    COUNT(*)::integer,
    ROUND(SUM(amount)::numeric, 2)::double precision,
    MIN(sale_date),
    MAX(sale_date),
    ROUND(AVG(gap_days)::numeric, 2)::double precision
FROM sale_gaps
GROUP BY customer_id;
"""


@dataclass
class DemoDataset:
    """Filas listas para INSERT en PostgreSQL (incluye columnas id)."""

    customers: list[tuple[Any, ...]]
    vehicles: list[tuple[Any, ...]]
    sales: list[tuple[Any, ...]]
    services: list[tuple[Any, ...]]
    insurance_policies: list[tuple[Any, ...]]
    service_appointments: list[tuple[Any, ...]]


def _validate_sales_vehicle_integrity(
    sale_rows: list[tuple[Any, ...]],
    *,
    valid_vehicle_ids: set[int],
    vehicle_meta: dict[int, dict[str, str | int]],
) -> None:
    """Garantiza que cada venta referencia un vehículo existente y del mismo cliente."""
    for row in sale_rows:
        sale_id, customer_id, vehicle_id, *_rest = row
        if vehicle_id is None:
            raise ValueError(f"Demo: venta id={sale_id} sin vehicle_id")
        vid = int(vehicle_id)
        if vid not in valid_vehicle_ids:
            raise ValueError(f"Demo: venta id={sale_id} referencia vehicle_id={vid} inexistente")
        owner = int(vehicle_meta[vid]["customer_id"])
        if owner != int(customer_id):
            raise ValueError(
                f"Demo: venta id={sale_id} (cliente {customer_id}) "
                f"no coincide con dueño del vehículo {vid} (cliente {owner})"
            )


def _normalize_pg_dsn(dsn: str) -> str:
    norm = dsn.strip()
    if "+psycopg" in norm:
        norm = norm.replace("postgresql+psycopg://", "postgresql://", 1)
    return norm


def _run_pg_statements(cur: Any, ddl: str) -> None:
    for raw in ddl.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        cur.execute(stmt)


def _postgres_demo_schema_current(cur: Any) -> bool:
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
    )
    existing = {str(r[0]) for r in cur.fetchall()}
    if not set(DEMO_TABLES).issubset(existing):
        return False

    def has_cols(table: str, cols: set[str]) -> bool:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        have = {str(r[0]).lower() for r in cur.fetchall()}
        return cols.issubset(have)

    checks = {
        "customers": {"gender", "age", "birth_date", "monthly_income", "risk_profile"},
        "vehicles": {"unit_type"},
        "sales": {"payment_method"},
        "service_appointments": {
            "customer_id",
            "vehicle_id",
            "appointment_date",
            "appointment_status",
        },
        "insurance_policies": {
            "customer_id",
            "vehicle_id",
            "policy_start_date",
            "policy_end_date",
            "annual_premium",
            "policy_status",
        },
    }
    for table, cols in checks.items():
        if not has_cols(table, cols):
            return False

    cur.execute(
        """
        SELECT is_nullable FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'sales' AND column_name = 'vehicle_id'
        """
    )
    row = cur.fetchone()
    if not row or str(row[0]).upper() != "NO":
        return False

    return True


def _count_table(cur: Any, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return int(cur.fetchone()[0])


def _insert_dataset(cur: Any, ds: DemoDataset) -> None:
    def many(sql: str, rows: list[tuple[Any, ...]]) -> None:
        if rows:
            cur.executemany(sql, rows)

    many(
        """
        INSERT INTO customers (
            id, customer_code, full_name, gender, age, birth_date, email, phone, city, state,
            segment, monthly_income, risk_profile, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ds.customers,
    )
    many(
        """
        INSERT INTO vehicles (
            id, customer_id, vin, plate, brand, model, unit_type, year, fuel_type, mileage, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ds.vehicles,
    )
    many(
        """
        INSERT INTO sales (
            id, customer_id, vehicle_id, sale_date, amount, channel, seller, payment_method, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ds.sales,
    )
    many(
        """
        INSERT INTO services (
            id, customer_id, vehicle_id, service_date, service_type, cost, status, workshop, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ds.services,
    )
    many(
        """
        INSERT INTO insurance_policies (
            id, customer_id, vehicle_id, policy_start_date, policy_end_date, insurer,
            coverage_type, annual_premium, policy_status, claim_count, last_claim_date
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ds.insurance_policies,
    )
    many(
        """
        INSERT INTO service_appointments (
            id, customer_id, vehicle_id, appointment_date, service_type, appointment_status,
            workshop, cancellation_reason, attended, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ds.service_appointments,
    )


def generate_demo_dataset() -> DemoDataset:
    """Genera el mismo dataset que antes había en SQLite demo (determinista)."""
    rnd = random.Random(20260324)

    male_first_names = ["Luis", "Carlos", "Jorge", "Miguel", "Jose", "Pedro", "Juan", "Hector"]
    female_first_names = ["Ana", "Sofia", "Fernanda", "Laura", "Daniela", "Mariana", "Karla", "Patricia"]
    last_names = [
        "Lopez",
        "Hernandez",
        "Garcia",
        "Martinez",
        "Torres",
        "Ramirez",
        "Vargas",
        "Mendoza",
        "Jimenez",
        "Sanchez",
    ]
    states = [
        "CDMX",
        "Jalisco",
        "Nuevo Leon",
        "Queretaro",
        "Puebla",
        "Yucatan",
        "Guanajuato",
    ]
    cities = {
        "CDMX": ["Benito Juarez", "Coyoacan", "Miguel Hidalgo"],
        "Jalisco": ["Guadalajara", "Zapopan", "Tlaquepaque"],
        "Nuevo Leon": ["Monterrey", "San Nicolas", "Guadalupe"],
        "Queretaro": ["Queretaro", "El Marques", "Corregidora"],
        "Puebla": ["Puebla", "Cholula", "Tehuacan"],
        "Yucatan": ["Merida", "Valladolid", "Progreso"],
        "Guanajuato": ["Leon", "Irapuato", "Celaya"],
    }
    segments = ["Retail", "Empresarial", "Premium"]
    channels = ["Showroom", "Digital", "Referido", "Flotillas"]
    sellers = ["Alberto Ruiz", "Diana Perez", "Mario Cruz", "Elena Soto"]
    payment_methods = ["Contado", "Financiamiento", "Leasing"]
    sale_statuses = ["cerrada", "facturada", "entregada"]
    service_types = [
        "Mantenimiento preventivo",
        "Cambio de aceite",
        "Revision de frenos",
        "Alineacion y balanceo",
        "Servicio mayor",
    ]
    service_statuses = ["completado", "entregado", "facturado"]
    appointment_statuses = ["completada", "programada", "no_show", "cancelada"]
    workshops = ["Taller Norte", "Taller Centro", "Taller Sur"]
    insurers = ["AXA", "GNP", "Qualitas", "Chubb", "HDI"]
    coverage_types = {
        "Hatchback": ["Limitada", "Amplia"],
        "Sedan": ["Limitada", "Amplia"],
        "SUV": ["Amplia", "Amplia Plus"],
        "Deportivo": ["Amplia Plus"],
        "Van": ["Amplia", "Amplia Plus"],
        "Pickup": ["Amplia", "Amplia Plus"],
    }

    customers_no_id: list[tuple[Any, ...]] = []
    today = date.today()
    for idx in range(1, 161):
        gender = rnd.choices(["Hombre", "Mujer"], weights=[51, 49], k=1)[0]
        first = rnd.choice(male_first_names if gender == "Hombre" else female_first_names)
        last = rnd.choice(last_names)
        last2 = rnd.choice(last_names)
        full_name = f"{first} {last} {last2}"
        age = _choose_customer_age(rnd)
        birth_year = today.year - age
        birth_date = date(birth_year, rnd.randint(1, 12), rnd.randint(1, 28))
        age = _age_from_birth_date(today, birth_date)
        state = rnd.choice(states)
        city = rnd.choice(cities[state])
        segment = rnd.choices(segments, weights=[54, 29, 17], k=1)[0]
        if segment == "Retail":
            monthly_income = round(rnd.uniform(14000, 42000), 2)
        elif segment == "Empresarial":
            monthly_income = round(rnd.uniform(28000, 85000), 2)
        else:
            monthly_income = round(rnd.uniform(60000, 185000), 2)
        risk_profile = _choose_risk_profile(rnd, age)
        created = today - timedelta(days=rnd.randint(20, 900))
        email = f"cliente{idx:03d}@demo.local"
        phone = f"55{rnd.randint(10000000, 99999999)}"
        customers_no_id.append(
            (
                f"C{idx:05d}",
                full_name,
                gender,
                age,
                birth_date.isoformat(),
                email,
                phone,
                city,
                state,
                segment,
                monthly_income,
                risk_profile,
                created.isoformat(),
            )
        )

    customer_profiles: dict[int, dict[str, Any]] = {}
    customer_rows: list[tuple[Any, ...]] = []
    for cid, row in enumerate(customers_no_id, start=1):
        customer_profiles[cid] = {
            "gender": row[2],
            "age": int(row[3]),
            "risk_profile": row[11],
        }
        customer_rows.append((cid, *row))

    customer_ids = sorted(customer_profiles)

    vehicles_no_id: list[tuple[Any, ...]] = []
    vehicle_owner: list[tuple[int, int]] = []
    vehicle_meta: dict[int, dict[str, str | int]] = {}
    vehicle_id_seq = 1
    for customer_id in customer_ids:
        profile = customer_profiles[customer_id]
        age = int(profile["age"])
        gender = str(profile["gender"])
        preferred_unit = _preferred_unit_type(age, gender, rnd)
        qty = rnd.choices([1, 2, 3], weights=[55, 35, 10], k=1)[0]
        for idx_vehicle in range(qty):
            if idx_vehicle == 0:
                unit_type = preferred_unit
            else:
                unit_type = rnd.choices(
                    [preferred_unit, "SUV", "Sedan", "Pickup", "Van", "Hatchback", "Deportivo"],
                    weights=[45, 20, 14, 8, 5, 5, 3],
                    k=1,
                )[0]
            brand, model = _unit_type_model(rnd, unit_type)
            year = rnd.randint(2016, today.year)
            fuel = _fuel_type_for_unit(rnd, unit_type)
            mileage = rnd.randint(5000, 180000)
            created = today - timedelta(days=rnd.randint(10, 1500))
            vin = f"VIN{vehicle_id_seq:014d}"
            plate = f"D{rnd.randint(1000,9999)}{chr(65+rnd.randint(0,25))}{chr(65+rnd.randint(0,25))}"
            vehicles_no_id.append(
                (
                    vehicle_id_seq,
                    customer_id,
                    vin,
                    plate,
                    brand,
                    model,
                    unit_type,
                    year,
                    fuel,
                    mileage,
                    created.isoformat(),
                )
            )
            vehicle_owner.append((vehicle_id_seq, customer_id))
            vehicle_meta[vehicle_id_seq] = {
                "customer_id": customer_id,
                "unit_type": unit_type,
                "created_at": created.isoformat(),
            }
            vehicle_id_seq += 1

    customer_to_vehicles: dict[int, list[int]] = {cid: [] for cid in customer_ids}
    for vid, cid in vehicle_owner:
        customer_to_vehicles[cid].append(vid)

    sales_no_id: list[tuple[Any, ...]] = []
    sales_by_vehicle: dict[int, list[date]] = {}
    for customer_id in customer_ids:
        v_ids = customer_to_vehicles[customer_id]
        qty = rnd.choices([0, 1, 2, 3, 4], weights=[8, 35, 30, 18, 9], k=1)[0]
        if qty == 0:
            continue

        first_sale = today - timedelta(days=rnd.randint(420, 1800))
        sale_dates = [first_sale]
        for _ in range(1, qty):
            next_sale = sale_dates[-1] + timedelta(days=rnd.randint(220, 780))
            if next_sale >= today - timedelta(days=5):
                break
            sale_dates.append(next_sale)

        if not v_ids:
            continue
        for sale_date in sale_dates:
            vehicle_id = rnd.choice(v_ids)
            unit_type = str(vehicle_meta[vehicle_id]["unit_type"])
            amount = _sale_amount_for_unit(rnd, unit_type)
            channel = rnd.choice(channels)
            seller = rnd.choice(sellers)
            payment_method = rnd.choices(payment_methods, weights=[24, 62, 14], k=1)[0]
            status = rnd.choice(sale_statuses)
            sales_no_id.append(
                (
                    customer_id,
                    vehicle_id,
                    sale_date.isoformat(),
                    amount,
                    channel,
                    seller,
                    payment_method,
                    status,
                )
            )
            sales_by_vehicle.setdefault(vehicle_id, []).append(sale_date)

    sale_rows = [(i, *t) for i, t in enumerate(sales_no_id, start=1)]

    _validate_sales_vehicle_integrity(
        sale_rows,
        valid_vehicle_ids={v[0] for v in vehicles_no_id},
        vehicle_meta=vehicle_meta,
    )

    services_no_id: list[tuple[Any, ...]] = []
    for customer_id in customer_ids:
        v_ids = customer_to_vehicles[customer_id]
        for vehicle_id in v_ids:
            qty = rnd.choices([1, 2, 3, 4], weights=[30, 35, 25, 10], k=1)[0]
            for _ in range(qty):
                service_date = today - timedelta(days=rnd.randint(1, 540))
                stype = rnd.choice(service_types)
                unit_type = str(vehicle_meta.get(vehicle_id, {}).get("unit_type", "Sedan"))
                cost = _service_cost_for_unit(rnd, unit_type)
                status = rnd.choice(service_statuses)
                workshop = rnd.choice(workshops)
                notes = "Generado para demo"
                services_no_id.append(
                    (
                        customer_id,
                        vehicle_id,
                        service_date.isoformat(),
                        stype,
                        cost,
                        status,
                        workshop,
                        notes,
                    )
                )

    service_rows = [(i, *t) for i, t in enumerate(services_no_id, start=1)]

    service_appointments_no_id: list[tuple[Any, ...]] = []
    for customer_id in customer_ids:
        v_ids = customer_to_vehicles[customer_id]
        for vehicle_id in v_ids:
            qty = rnd.choices([1, 2, 3], weights=[45, 38, 17], k=1)[0]
            for _ in range(qty):
                appointment_date = today + timedelta(days=rnd.randint(-120, 120))
                appointment_status = rnd.choices(
                    appointment_statuses,
                    weights=[42, 33, 14, 11],
                    k=1,
                )[0]
                stype = rnd.choice(service_types)
                workshop = rnd.choice(workshops)
                cancellation_reason = None
                attended = 1 if appointment_status == "completada" else 0
                if appointment_status == "cancelada":
                    cancellation_reason = rnd.choice(
                        [
                            "Cliente reagendó",
                            "Refacción no disponible",
                            "Conflicto de agenda",
                        ]
                    )
                created_at = (appointment_date - timedelta(days=rnd.randint(1, 20))).isoformat()
                updated_at = (
                    appointment_date + timedelta(days=rnd.randint(0, 5))
                    if appointment_status in {"completada", "no_show", "cancelada"}
                    else appointment_date - timedelta(days=rnd.randint(0, 2))
                ).isoformat()
                service_appointments_no_id.append(
                    (
                        customer_id,
                        vehicle_id,
                        appointment_date.isoformat(),
                        stype,
                        appointment_status,
                        workshop,
                        cancellation_reason,
                        attended,
                        created_at,
                        updated_at,
                    )
                )

    service_appointments_no_id = _ensure_min_future_appointments(
        service_appointments_no_id,
        customer_ids=customer_ids,
        customer_to_vehicles=customer_to_vehicles,
        today=today,
        rnd=rnd,
        service_types=service_types,
        workshops=workshops,
        min_future_count=100,
    )

    appointment_rows = [(i, *t) for i, t in enumerate(service_appointments_no_id, start=1)]

    insurance_no_id: list[tuple[Any, ...]] = []
    for vehicle_id, customer_id in vehicle_owner:
        if rnd.random() > 0.76:
            continue

        profile = customer_profiles[customer_id]
        risk_profile = str(profile["risk_profile"])
        unit_type = str(vehicle_meta.get(vehicle_id, {}).get("unit_type", "Sedan"))
        insurer = rnd.choice(insurers)
        coverage = rnd.choice(coverage_types[unit_type])
        annual_premium = _insurance_premium_for_unit(unit_type, risk_profile, rnd)

        status = rnd.choices(["activa", "vencida", "cancelada"], weights=[60, 32, 8], k=1)[0]
        if status == "activa":
            policy_end = today + timedelta(days=rnd.randint(10, 350))
            if rnd.random() < 0.3:
                policy_end = today + timedelta(days=rnd.randint(5, 60))
            policy_start = policy_end - timedelta(days=365)
        elif status == "vencida":
            policy_end = today - timedelta(days=rnd.randint(15, 550))
            policy_start = policy_end - timedelta(days=365)
        else:
            sale_dates = sorted(sales_by_vehicle.get(vehicle_id, []))
            base = sale_dates[-1] if sale_dates else today - timedelta(days=rnd.randint(200, 1200))
            policy_start = base - timedelta(days=rnd.randint(20, 120))
            policy_end = policy_start + timedelta(days=rnd.randint(90, 240))

        claim_count = rnd.choices(
            [0, 1, 2, 3],
            weights=[55, 30, 12, 3] if risk_profile != "alto" else [36, 34, 22, 8],
            k=1,
        )[0]
        last_claim_date = None
        if claim_count > 0:
            claim_end = min(policy_end, today)
            if policy_start < claim_end:
                last_claim = policy_start + timedelta(days=rnd.randint(10, (claim_end - policy_start).days))
                last_claim_date = last_claim.isoformat()

        insurance_no_id.append(
            (
                customer_id,
                vehicle_id,
                policy_start.isoformat(),
                policy_end.isoformat(),
                insurer,
                coverage,
                annual_premium,
                status,
                claim_count,
                last_claim_date,
            )
        )

    insurance_rows = [(i, *t) for i, t in enumerate(insurance_no_id, start=1)]

    return DemoDataset(
        customers=customer_rows,
        vehicles=vehicles_no_id,
        sales=sale_rows,
        services=service_rows,
        insurance_policies=insurance_rows,
        service_appointments=appointment_rows,
    )


def ensure_demo_postgres(
    dsn: str | None = None,
    *,
    force_rebuild: bool = False,
) -> dict[str, int]:
    """
    Garantiza tablas demo en PostgreSQL y refresca MVs.

    Usa DEMO_DWH_URL o DWH_URL si dsn es None.
    """
    import psycopg

    resolved = (dsn or os.getenv("DEMO_DWH_URL") or os.getenv("DWH_URL") or "").strip()
    if not resolved or "postgresql" not in resolved.lower():
        raise ValueError(
            "Se requiere una URL PostgreSQL (postgresql+psycopg://...) en dsn, "
            "DEMO_DWH_URL o DWH_URL."
        )

    conn = psycopg.connect(_normalize_pg_dsn(resolved))
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            need_full = force_rebuild
            if not need_full:
                if not _postgres_demo_schema_current(cur):
                    need_full = True
                else:
                    cur.execute("SELECT COUNT(*) FROM customers")
                    need_full = int(cur.fetchone()[0]) == 0

            if need_full:
                for t in POSTGRES_DROP_ORDER:
                    cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
                _run_pg_statements(cur, POSTGRES_DDL)

        conn.autocommit = False
        with conn.cursor() as cur:
            if need_full:
                ds = generate_demo_dataset()
                _insert_dataset(cur, ds)
            _run_pg_statements(cur, REFRESH_MATERIALIZED_DEMO_SQL)
        conn.commit()

        conn.autocommit = True
        with conn.cursor() as cur:
            return {
                "customers": _count_table(cur, "customers"),
                "vehicles": _count_table(cur, "vehicles"),
                "sales": _count_table(cur, "sales"),
                "services": _count_table(cur, "services"),
                "service_appointments": _count_table(cur, "service_appointments"),
                "insurance_policies": _count_table(cur, "insurance_policies"),
                "mv_sales_monthly": _count_table(cur, "mv_sales_monthly"),
                "mv_customer_lifecycle": _count_table(cur, "mv_customer_lifecycle"),
            }
    finally:
        conn.close()


def _age_from_birth_date(today: date, birth_date: date) -> int:
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _choose_customer_age(rnd: random.Random) -> int:
    bucket = rnd.choices(
        ["20-30", "31-39", "40-50", "51-65", "66-75"],
        weights=[20, 27, 31, 18, 4],
        k=1,
    )[0]
    if bucket == "20-30":
        return rnd.randint(20, 30)
    if bucket == "31-39":
        return rnd.randint(31, 39)
    if bucket == "40-50":
        return rnd.randint(40, 50)
    if bucket == "51-65":
        return rnd.randint(51, 65)
    return rnd.randint(66, 75)


def _choose_risk_profile(rnd: random.Random, age: int) -> str:
    if age <= 25:
        return rnd.choices(["alto", "medio", "bajo"], weights=[38, 47, 15], k=1)[0]
    if age <= 39:
        return rnd.choices(["alto", "medio", "bajo"], weights=[20, 55, 25], k=1)[0]
    if age <= 55:
        return rnd.choices(["alto", "medio", "bajo"], weights=[13, 50, 37], k=1)[0]
    return rnd.choices(["alto", "medio", "bajo"], weights=[8, 42, 50], k=1)[0]


def _preferred_unit_type(age: int, gender: str, rnd: random.Random) -> str:
    if 20 <= age <= 30:
        return rnd.choices(["Deportivo", "Hatchback", "Sedan"], weights=[44, 34, 22], k=1)[0]
    if 31 <= age <= 39:
        return rnd.choices(["SUV", "Sedan", "Hatchback"], weights=[42, 36, 22], k=1)[0]
    if 40 <= age <= 50 and gender == "Mujer":
        return rnd.choices(["Van", "SUV", "Sedan"], weights=[46, 34, 20], k=1)[0]
    if 40 <= age <= 50:
        return rnd.choices(["SUV", "Pickup", "Sedan"], weights=[48, 30, 22], k=1)[0]
    return rnd.choices(["SUV", "Sedan", "Pickup"], weights=[45, 35, 20], k=1)[0]


def _unit_type_model(rnd: random.Random, unit_type: str) -> tuple[str, str]:
    mapping: dict[str, list[tuple[str, str]]] = {
        "SUV": [
            ("Toyota", "RAV4"),
            ("Volkswagen", "Tiguan"),
            ("Kia", "Sportage"),
            ("Nissan", "Kicks"),
            ("Chevrolet", "Tracker"),
            ("Volkswagen", "Taos"),
            ("Kia", "Seltos"),
        ],
        "Sedan": [
            ("Nissan", "Sentra"),
            ("Toyota", "Corolla"),
            ("Volkswagen", "Jetta"),
            ("Kia", "Forte"),
            ("Chevrolet", "Onix"),
            ("Nissan", "Versa"),
        ],
        "Deportivo": [
            ("Ford", "Mustang"),
            ("Toyota", "GR86"),
            ("Chevrolet", "Camaro"),
            ("Mazda", "MX-5"),
        ],
        "Van": [
            ("Toyota", "Hiace"),
            ("Kia", "Carnival"),
            ("Chevrolet", "Express"),
            ("Volkswagen", "Transporter"),
        ],
        "Pickup": [
            ("Toyota", "Hilux"),
            ("Nissan", "NP300"),
            ("Chevrolet", "S10"),
            ("Ford", "Ranger"),
        ],
        "Hatchback": [
            ("Toyota", "Yaris"),
            ("Kia", "Rio"),
            ("Chevrolet", "Onix"),
            ("Volkswagen", "Polo"),
        ],
    }
    return rnd.choice(mapping[unit_type])


def _fuel_type_for_unit(rnd: random.Random, unit_type: str) -> str:
    if unit_type == "Pickup":
        return rnd.choices(["Diesel", "Gasolina"], weights=[60, 40], k=1)[0]
    if unit_type == "Van":
        return rnd.choices(["Diesel", "Gasolina", "Hibrido"], weights=[45, 40, 15], k=1)[0]
    if unit_type == "SUV":
        return rnd.choices(["Gasolina", "Hibrido", "Diesel"], weights=[60, 28, 12], k=1)[0]
    return rnd.choices(["Gasolina", "Hibrido"], weights=[82, 18], k=1)[0]


def _sale_amount_for_unit(rnd: random.Random, unit_type: str) -> float:
    ranges: dict[str, tuple[int, int]] = {
        "Hatchback": (220000, 420000),
        "Sedan": (260000, 560000),
        "SUV": (420000, 980000),
        "Deportivo": (700000, 1450000),
        "Van": (480000, 980000),
        "Pickup": (430000, 900000),
    }
    low, high = ranges[unit_type]
    return round(rnd.uniform(low, high), 2)


def _service_cost_for_unit(rnd: random.Random, unit_type: str) -> float:
    ranges: dict[str, tuple[int, int]] = {
        "Hatchback": (1000, 9000),
        "Sedan": (1200, 12000),
        "SUV": (1600, 16000),
        "Deportivo": (3000, 28000),
        "Van": (1800, 17000),
        "Pickup": (1800, 15000),
    }
    low, high = ranges[unit_type]
    return round(rnd.uniform(low, high), 2)


def _insurance_premium_for_unit(unit_type: str, risk_profile: str, rnd: random.Random) -> float:
    base = {
        "Hatchback": 10500,
        "Sedan": 13200,
        "SUV": 17600,
        "Deportivo": 26500,
        "Van": 16800,
        "Pickup": 18800,
    }[unit_type]
    risk_multiplier = {"bajo": 0.9, "medio": 1.1, "alto": 1.3}[risk_profile]
    return round(base * risk_multiplier * rnd.uniform(0.9, 1.12), 2)


def _ensure_min_future_appointments(
    appointments: list[tuple[object, ...]],
    *,
    customer_ids: list[int],
    customer_to_vehicles: dict[int, list[int]],
    today: date,
    rnd: random.Random,
    service_types: list[str],
    workshops: list[str],
    min_future_count: int = 100,
) -> list[tuple[object, ...]]:
    """Garantiza un mínimo de citas futuras en ventana de 3 meses."""
    start_future = today + timedelta(days=1)
    end_future = today + timedelta(days=90)

    current_future_count = 0
    for row in appointments:
        appointment_date_raw = str(row[2])
        appointment_date = date.fromisoformat(appointment_date_raw)
        if start_future <= appointment_date <= end_future:
            current_future_count += 1

    missing = max(0, min_future_count - current_future_count)
    if missing == 0:
        return appointments

    for _ in range(missing):
        customer_id = rnd.choice(customer_ids)
        vehicles = customer_to_vehicles.get(customer_id) or []
        if not vehicles:
            continue
        vehicle_id = rnd.choice(vehicles)
        appointment_date = today + timedelta(days=rnd.randint(1, 90))
        service_type = rnd.choice(service_types)
        workshop = rnd.choice(workshops)
        appointment_status = "programada"
        cancellation_reason = None
        attended = 0
        created_at = (appointment_date - timedelta(days=rnd.randint(1, 25))).isoformat()
        updated_at = created_at
        appointments.append(
            (
                customer_id,
                vehicle_id,
                appointment_date.isoformat(),
                service_type,
                appointment_status,
                workshop,
                cancellation_reason,
                attended,
                created_at,
                updated_at,
            )
        )
    return appointments
