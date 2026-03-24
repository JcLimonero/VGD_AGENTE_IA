from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = PROJECT_ROOT / "demo"
DEMO_DB_PATH = DEMO_DIR / "demo_dwh.sqlite3"
DEMO_DWH_URL = f"sqlite+pysqlite:///{DEMO_DB_PATH.as_posix()}"
DEMO_SCHEMA_HINT_FILE = (PROJECT_ROOT / "schema_hint_demo.txt").as_posix()
DEMO_TABLES = ("insurance_policies", "services", "sales", "vehicles", "customers")


def ensure_demo_db(db_path: str | None = None) -> dict[str, int]:
    """Crea y carga una base de datos demo enriquecida."""
    path = Path(db_path) if db_path else DEMO_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path.as_posix())
    conn.execute("PRAGMA foreign_keys = ON;")
    if not _is_schema_current(conn):
        _rebuild_demo_data(conn)
    elif _count(conn, "customers") == 0:
        _seed_data(conn)

    counts = {
        "customers": _count(conn, "customers"),
        "vehicles": _count(conn, "vehicles"),
        "sales": _count(conn, "sales"),
        "services": _count(conn, "services"),
        "insurance_policies": _count(conn, "insurance_policies"),
    }
    conn.close()
    return counts


def _count(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return int(cur.fetchone()[0])


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    )
    return cur.fetchone() is not None


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row[1]).lower() == column.lower() for row in rows)


def _is_schema_current(conn: sqlite3.Connection) -> bool:
    required_tables = set(DEMO_TABLES)
    existing_tables = {
        str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not required_tables.issubset(existing_tables):
        return False

    required_columns = {
        "customers": {"gender", "age", "birth_date", "monthly_income", "risk_profile"},
        "vehicles": {"unit_type"},
        "sales": {"payment_method"},
        "insurance_policies": {
            "customer_id",
            "vehicle_id",
            "policy_start_date",
            "policy_end_date",
            "annual_premium",
            "policy_status",
        },
    }
    for table_name, columns in required_columns.items():
        for column in columns:
            if not _has_column(conn, table_name, column):
                return False
    return True


def _rebuild_demo_data(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF;")
    for table in DEMO_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table};")
    conn.execute("PRAGMA foreign_keys = ON;")
    _create_schema(conn)
    _seed_data(conn)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            gender TEXT NOT NULL,
            age INTEGER NOT NULL,
            birth_date TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            city TEXT,
            state TEXT,
            segment TEXT NOT NULL,
            monthly_income REAL NOT NULL,
            risk_profile TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vin TEXT NOT NULL UNIQUE,
            plate TEXT NOT NULL UNIQUE,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            unit_type TEXT NOT NULL,
            year INTEGER NOT NULL,
            fuel_type TEXT NOT NULL,
            mileage INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER,
            sale_date TEXT NOT NULL,
            amount REAL NOT NULL,
            channel TEXT NOT NULL,
            seller TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            service_date TEXT NOT NULL,
            service_type TEXT NOT NULL,
            cost REAL NOT NULL,
            status TEXT NOT NULL,
            workshop TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
        );

        CREATE TABLE IF NOT EXISTS insurance_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            policy_start_date TEXT NOT NULL,
            policy_end_date TEXT NOT NULL,
            insurer TEXT NOT NULL,
            coverage_type TEXT NOT NULL,
            annual_premium REAL NOT NULL,
            policy_status TEXT NOT NULL,
            claim_count INTEGER NOT NULL,
            last_claim_date TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
        );

        CREATE INDEX IF NOT EXISTS idx_customers_state ON customers(state);
        CREATE INDEX IF NOT EXISTS idx_customers_age ON customers(age);
        CREATE INDEX IF NOT EXISTS idx_customers_gender ON customers(gender);
        CREATE INDEX IF NOT EXISTS idx_vehicles_customer ON vehicles(customer_id);
        CREATE INDEX IF NOT EXISTS idx_vehicles_unit_type ON vehicles(unit_type);
        CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
        CREATE INDEX IF NOT EXISTS idx_sales_vehicle ON sales(vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
        CREATE INDEX IF NOT EXISTS idx_services_customer ON services(customer_id);
        CREATE INDEX IF NOT EXISTS idx_services_vehicle ON services(vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_services_date ON services(service_date);
        CREATE INDEX IF NOT EXISTS idx_policies_customer ON insurance_policies(customer_id);
        CREATE INDEX IF NOT EXISTS idx_policies_vehicle ON insurance_policies(vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_policies_status ON insurance_policies(policy_status);
        """
    )


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


def _seed_data(conn: sqlite3.Connection) -> None:
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

    customers = []
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
        customers.append(
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

    conn.executemany(
        """
        INSERT INTO customers (
            customer_code, full_name, gender, age, birth_date, email, phone, city, state, segment, monthly_income, risk_profile, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    customer_profiles = {
        int(row[0]): {"gender": row[1], "age": int(row[2]), "risk_profile": row[3]}
        for row in conn.execute("SELECT id, gender, age, risk_profile FROM customers ORDER BY id")
    }
    customer_ids = sorted(customer_profiles)

    vehicles = []
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
            vehicles.append(
                (
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

    conn.executemany(
        """
        INSERT INTO vehicles (
            customer_id, vin, plate, brand, model, unit_type, year, fuel_type, mileage, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        vehicles,
    )

    customer_to_vehicles: dict[int, list[int]] = {customer_id: [] for customer_id in customer_ids}
    for vehicle_id, customer_id in vehicle_owner:
        customer_to_vehicles[customer_id].append(vehicle_id)

    sales = []
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

        for sale_date in sale_dates:
            vehicle_id = rnd.choice(v_ids) if v_ids else None
            unit_type = str(vehicle_meta.get(vehicle_id or 0, {}).get("unit_type", "Sedan"))
            amount = _sale_amount_for_unit(rnd, unit_type)
            channel = rnd.choice(channels)
            seller = rnd.choice(sellers)
            payment_method = rnd.choices(payment_methods, weights=[24, 62, 14], k=1)[0]
            status = rnd.choice(sale_statuses)
            sales.append(
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
            if vehicle_id is not None:
                sales_by_vehicle.setdefault(vehicle_id, []).append(sale_date)

    conn.executemany(
        """
        INSERT INTO sales (
            customer_id, vehicle_id, sale_date, amount, channel, seller, payment_method, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sales,
    )

    services = []
    for customer_id in customer_ids:
        v_ids = customer_to_vehicles[customer_id]
        for vehicle_id in v_ids:
            qty = rnd.choices([1, 2, 3, 4], weights=[30, 35, 25, 10], k=1)[0]
            for _ in range(qty):
                service_date = today - timedelta(days=rnd.randint(1, 540))
                service_type = rnd.choice(service_types)
                unit_type = str(vehicle_meta.get(vehicle_id, {}).get("unit_type", "Sedan"))
                cost = _service_cost_for_unit(rnd, unit_type)
                status = rnd.choice(service_statuses)
                workshop = rnd.choice(workshops)
                notes = "Generado para demo"
                services.append(
                    (
                        customer_id,
                        vehicle_id,
                        service_date.isoformat(),
                        service_type,
                        cost,
                        status,
                        workshop,
                        notes,
                    )
                )

    conn.executemany(
        """
        INSERT INTO services (
            customer_id, vehicle_id, service_date, service_type, cost, status, workshop, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        services,
    )

    insurance_policies = []
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

        insurance_policies.append(
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

    conn.executemany(
        """
        INSERT INTO insurance_policies (
            customer_id,
            vehicle_id,
            policy_start_date,
            policy_end_date,
            insurer,
            coverage_type,
            annual_premium,
            policy_status,
            claim_count,
            last_claim_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        insurance_policies,
    )

    conn.commit()
