-- Crear schema para plataforma (opcional, usar public si prefieres simplicidad)
-- CREATE SCHEMA IF NOT EXISTS platform;

-- ============ Roles de plataforma ============
CREATE TABLE IF NOT EXISTS platform_roles (
    id                SERIAL PRIMARY KEY,
    name              TEXT NOT NULL UNIQUE,
    description       TEXT NOT NULL DEFAULT '',
    is_base_role      BOOLEAN NOT NULL DEFAULT false,
    can_create_users  BOOLEAN NOT NULL DEFAULT false,
    can_access_config BOOLEAN NOT NULL DEFAULT false,
    all_agencies      BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Permisos de agencias por rol (cuando all_agencies=false)
CREATE TABLE IF NOT EXISTS role_agency_permissions (
    role_id     INT NOT NULL REFERENCES platform_roles(id) ON DELETE CASCADE,
    id_agency   TEXT NOT NULL,
    all_objects BOOLEAN NOT NULL DEFAULT true,
    PRIMARY KEY (role_id, id_agency)
);

-- Permisos de objetos DWH por rol y agencia (cuando all_objects=false)
CREATE TABLE IF NOT EXISTS role_object_permissions (
    role_id     INT NOT NULL REFERENCES platform_roles(id) ON DELETE CASCADE,
    id_agency   TEXT NOT NULL,
    dwh_object  TEXT NOT NULL,
    PRIMARY KEY (role_id, id_agency, dwh_object)
);

CREATE INDEX IF NOT EXISTS idx_role_agency ON role_agency_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_object ON role_object_permissions(role_id, id_agency);

-- Roles base
INSERT INTO platform_roles (name, description, is_base_role, can_create_users, can_access_config, all_agencies)
VALUES
    ('sysadmin', 'Administrador del sistema con acceso completo', true, true, true, true),
    ('director', 'Director con acceso completo excepto configuración del sistema', true, true, false, true)
ON CONFLICT (name) DO NOTHING;

-- ============ Tabla de usuarios ============
CREATE TABLE IF NOT EXISTS platform_users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer', 'editor', 'admin')),
    role_id       INT REFERENCES platform_roles(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- Tabla de consultas guardadas
CREATE TABLE IF NOT EXISTS saved_queries (
    id                SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    title             TEXT NOT NULL,
    original_question TEXT NOT NULL,
    sql_text          TEXT NOT NULL,
    chart_type        TEXT NOT NULL DEFAULT 'table' CHECK (chart_type IN ('table', 'bar', 'line', 'kpi', 'pie', 'area')),
    chart_config      JSONB NOT NULL DEFAULT '{}',
    refresh_interval  INTERVAL,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    tags              TEXT[] DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices para saved_queries
CREATE INDEX IF NOT EXISTS idx_sq_user ON saved_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_sq_active_refresh ON saved_queries(is_active, refresh_interval)
    WHERE is_active AND refresh_interval IS NOT NULL;

-- Tabla de dashboards
CREATE TABLE IF NOT EXISTS dashboards (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT 'Mi Dashboard',
    is_default  BOOLEAN NOT NULL DEFAULT false,
    layout_cols INT NOT NULL DEFAULT 12 CHECK (layout_cols > 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índice para dashboards
CREATE INDEX IF NOT EXISTS idx_dashboards_user ON dashboards(user_id);

-- Tabla de widgets del dashboard
CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id              SERIAL PRIMARY KEY,
    dashboard_id    INT NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    saved_query_id  INT NOT NULL REFERENCES saved_queries(id) ON DELETE CASCADE,
    pos_x           INT NOT NULL DEFAULT 0 CHECK (pos_x >= 0),
    pos_y           INT NOT NULL DEFAULT 0 CHECK (pos_y >= 0),
    width           INT NOT NULL DEFAULT 6 CHECK (width > 0),
    height          INT NOT NULL DEFAULT 4 CHECK (height > 0),
    display_order   INT NOT NULL DEFAULT 0,
    widget_config   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices para dashboard_widgets
CREATE INDEX IF NOT EXISTS idx_dw_dashboard ON dashboard_widgets(dashboard_id);
CREATE INDEX IF NOT EXISTS idx_dw_query ON dashboard_widgets(saved_query_id);

-- Tabla de snapshots de resultados
CREATE TABLE IF NOT EXISTS query_snapshots (
    id              SERIAL PRIMARY KEY,
    saved_query_id  INT NOT NULL REFERENCES saved_queries(id) ON DELETE CASCADE,
    result_data     JSONB NOT NULL,
    row_count       INT NOT NULL CHECK (row_count >= 0),
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms     DOUBLE PRECISION NOT NULL CHECK (duration_ms >= 0),
    success         BOOLEAN NOT NULL DEFAULT true,
    error_message   TEXT
);

-- Índices para query_snapshots
CREATE INDEX IF NOT EXISTS idx_qs_query_time ON query_snapshots(saved_query_id, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_qs_cleanup ON query_snapshots(saved_query_id, executed_at);

-- Tabla de log de refrescos
CREATE TABLE IF NOT EXISTS refresh_log (
    id              SERIAL PRIMARY KEY,
    saved_query_id  INT NOT NULL REFERENCES saved_queries(id) ON DELETE CASCADE,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    success         BOOLEAN,
    duration_ms     DOUBLE PRECISION,
    error_message   TEXT
);

-- Índice para refresh_log
CREATE INDEX IF NOT EXISTS idx_rl_query_triggered ON refresh_log(saved_query_id, triggered_at DESC);

-- Usuario default: carlos.limon@nexusqtech.com / 00@Limonero (sysadmin)
INSERT INTO platform_users (username, display_name, password_hash, role, role_id)
VALUES (
    'carlos.limon@nexusqtech.com',
    'Carlos Limón',
    '$2b$12$uZDj1iVUhpcoJLzAr1/GFuqGLhYdijCIj3MR3QU3VlylsSDR8MMOe',
    'admin',
    (SELECT id FROM platform_roles WHERE name = 'sysadmin')
)
ON CONFLICT (username) DO NOTHING;

-- Dashboard por defecto para carlos.limon
INSERT INTO dashboards (user_id, title, is_default)
SELECT id, 'Mi Dashboard', true FROM platform_users WHERE username = 'carlos.limon@nexusqtech.com'
ON CONFLICT DO NOTHING;

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_saved_queries_updated_at BEFORE UPDATE ON saved_queries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dashboards_updated_at BEFORE UPDATE ON dashboards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Función para limpiar snapshots antiguos (mantener solo los últimos 10 por query)
CREATE OR REPLACE FUNCTION cleanup_old_snapshots()
RETURNS void AS $$
BEGIN
    DELETE FROM query_snapshots
    WHERE id IN (
        SELECT id FROM (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY saved_query_id ORDER BY executed_at DESC) as rn
            FROM query_snapshots
        ) t
        WHERE t.rn > 10
    );
END;
$$ LANGUAGE plpgsql;

-- Comentarios en las tablas
COMMENT ON TABLE platform_users IS 'Usuarios de la plataforma con roles y autenticación';
COMMENT ON TABLE saved_queries IS 'Consultas SQL guardadas generadas por el agente IA';
COMMENT ON TABLE dashboards IS 'Dashboards personalizados de cada usuario';
COMMENT ON TABLE dashboard_widgets IS 'Widgets que componen cada dashboard';
COMMENT ON TABLE query_snapshots IS 'Snapshots de resultados de consultas ejecutadas';
COMMENT ON TABLE refresh_log IS 'Log de ejecuciones programadas de consultas';