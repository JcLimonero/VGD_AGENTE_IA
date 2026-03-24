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


def ensure_demo_db(db_path: str | None = None) -> dict[str, int]:
    """Crea y carga una base de datos demo si no existe."""
    path = Path(db_path) if db_path else DEMO_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path.as_posix())
    conn.execute("PRAGMA foreign_keys = ON;")
    _create_schema(conn)

    if _count(conn, "customers") == 0:
        _seed_data(conn)

    counts = {
        "customers": _count(conn, "customers"),
        "vehicles": _count(conn, "vehicles"),
        "sales": _count(conn, "sales"),
        "services": _count(conn, "services"),
    }
    conn.close()
    return counts


def _count(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return int(cur.fetchone()[0])


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            city TEXT,
            state TEXT,
            segment TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vin TEXT NOT NULL UNIQUE,
            plate TEXT NOT NULL UNIQUE,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
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

        CREATE INDEX IF NOT EXISTS idx_customers_state ON customers(state);
        CREATE INDEX IF NOT EXISTS idx_vehicles_customer ON vehicles(customer_id);
        CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
        CREATE INDEX IF NOT EXISTS idx_sales_vehicle ON sales(vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_services_customer ON services(customer_id);
        CREATE INDEX IF NOT EXISTS idx_services_vehicle ON services(vehicle_id);
        """
    )


def _seed_data(conn: sqlite3.Connection) -> None:
    rnd = random.Random(20260324)

    first_names = [
        "Luis",
        "Ana",
        "Carlos",
        "Sofia",
        "Jorge",
        "Fernanda",
        "Miguel",
        "Laura",
        "Jose",
        "Daniela",
        "Pedro",
        "Mariana",
    ]
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

    brands_models = {
        "Nissan": ["Versa", "Sentra", "Kicks", "NP300"],
        "Toyota": ["Corolla", "Yaris", "Hilux", "RAV4"],
        "Chevrolet": ["Aveo", "Onix", "S10", "Tracker"],
        "Volkswagen": ["Jetta", "Vento", "Taos", "Tiguan"],
        "Kia": ["Rio", "Forte", "Seltos", "Sportage"],
    }
    fuel_types = ["Gasolina", "Diesel", "Hibrido"]
    channels = ["Showroom", "Digital", "Referido", "Flotillas"]
    sellers = ["Alberto Ruiz", "Diana Perez", "Mario Cruz", "Elena Soto"]
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

    customers = []
    today = date.today()
    for idx in range(1, 161):
        first = rnd.choice(first_names)
        last = rnd.choice(last_names)
        last2 = rnd.choice(last_names)
        full_name = f"{first} {last} {last2}"
        state = rnd.choice(states)
        city = rnd.choice(cities[state])
        segment = rnd.choice(segments)
        created = today - timedelta(days=rnd.randint(20, 900))
        email = f"cliente{idx:03d}@demo.local"
        phone = f"55{rnd.randint(10000000, 99999999)}"
        customers.append(
            (
                f"C{idx:05d}",
                full_name,
                email,
                phone,
                city,
                state,
                segment,
                created.isoformat(),
            )
        )

    conn.executemany(
        """
        INSERT INTO customers (
            customer_code, full_name, email, phone, city, state, segment, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    customer_ids = [row[0] for row in conn.execute("SELECT id FROM customers ORDER BY id")]

    vehicles = []
    vehicle_owner: list[tuple[int, int]] = []
    vehicle_id_seq = 1
    for customer_id in customer_ids:
        qty = rnd.choices([1, 2, 3], weights=[55, 35, 10], k=1)[0]
        for _ in range(qty):
            brand = rnd.choice(list(brands_models.keys()))
            model = rnd.choice(brands_models[brand])
            year = rnd.randint(2016, today.year)
            fuel = rnd.choices(fuel_types, weights=[70, 20, 10], k=1)[0]
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
                    year,
                    fuel,
                    mileage,
                    created.isoformat(),
                )
            )
            vehicle_owner.append((vehicle_id_seq, customer_id))
            vehicle_id_seq += 1

    conn.executemany(
        """
        INSERT INTO vehicles (
            customer_id, vin, plate, brand, model, year, fuel_type, mileage, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        vehicles,
    )

    customer_to_vehicles: dict[int, list[int]] = {customer_id: [] for customer_id in customer_ids}
    for vehicle_id, customer_id in vehicle_owner:
        customer_to_vehicles[customer_id].append(vehicle_id)

    sales = []
    for customer_id in customer_ids:
        v_ids = customer_to_vehicles[customer_id]
        qty = rnd.choices([0, 1, 2, 3], weights=[10, 45, 30, 15], k=1)[0]
        for _ in range(qty):
            vehicle_id = rnd.choice(v_ids) if v_ids else None
            sale_date = today - timedelta(days=rnd.randint(1, 720))
            amount = round(rnd.uniform(220000, 980000), 2)
            channel = rnd.choice(channels)
            seller = rnd.choice(sellers)
            status = rnd.choice(sale_statuses)
            sales.append(
                (
                    customer_id,
                    vehicle_id,
                    sale_date.isoformat(),
                    amount,
                    channel,
                    seller,
                    status,
                )
            )

    conn.executemany(
        """
        INSERT INTO sales (
            customer_id, vehicle_id, sale_date, amount, channel, seller, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
                cost = round(rnd.uniform(1200, 18500), 2)
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

    conn.commit()
