-- ============================================================
-- MIGRACIÓN: Sistema de roles dinámicos con permisos por agencia
-- Ejecutar contra la base de datos vgd_platform
-- ============================================================

-- 1. Tabla de roles de plataforma
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

COMMENT ON TABLE platform_roles IS 'Roles de plataforma: base (sysadmin/director) y dinámicos con permisos por agencia';
COMMENT ON COLUMN platform_roles.is_base_role IS 'true = rol base del sistema (no se puede editar ni eliminar)';
COMMENT ON COLUMN platform_roles.all_agencies IS 'true = acceso a todas las agencias del DWH sin restricción';

-- 2. Permisos de agencias por rol
CREATE TABLE IF NOT EXISTS role_agency_permissions (
    role_id     INT NOT NULL REFERENCES platform_roles(id) ON DELETE CASCADE,
    id_agency   TEXT NOT NULL,
    all_objects BOOLEAN NOT NULL DEFAULT true,
    PRIMARY KEY (role_id, id_agency)
);

COMMENT ON TABLE role_agency_permissions IS 'Agencias específicas a las que tiene acceso un rol (cuando all_agencies=false)';
COMMENT ON COLUMN role_agency_permissions.all_objects IS 'true = acceso a todos los objetos DWH de esa agencia';

-- 3. Permisos de objetos DWH por rol y agencia
CREATE TABLE IF NOT EXISTS role_object_permissions (
    role_id     INT NOT NULL REFERENCES platform_roles(id) ON DELETE CASCADE,
    id_agency   TEXT NOT NULL,
    dwh_object  TEXT NOT NULL,
    PRIMARY KEY (role_id, id_agency, dwh_object)
);

COMMENT ON TABLE role_object_permissions IS 'Objetos DWH específicos accesibles por rol+agencia (cuando all_objects=false)';

-- Índices
CREATE INDEX IF NOT EXISTS idx_role_agency ON role_agency_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_object ON role_object_permissions(role_id, id_agency);

-- 4. Roles base del sistema
INSERT INTO platform_roles (name, description, is_base_role, can_create_users, can_access_config, all_agencies)
VALUES
    ('sysadmin', 'Administrador del sistema con acceso completo', true, true, true, true),
    ('director', 'Director con acceso completo excepto configuración del sistema', true, true, false, true)
ON CONFLICT (name) DO NOTHING;

-- 5. Agregar columna role_id a platform_users
ALTER TABLE platform_users ADD COLUMN IF NOT EXISTS role_id INT REFERENCES platform_roles(id);

-- 6. Migrar usuarios existentes
--    admin → sysadmin, editor/viewer → director
UPDATE platform_users
SET role_id = (SELECT id FROM platform_roles WHERE name = 'sysadmin')
WHERE role = 'admin' AND role_id IS NULL;

UPDATE platform_users
SET role_id = (SELECT id FROM platform_roles WHERE name = 'director')
WHERE role IN ('editor', 'viewer') AND role_id IS NULL;

-- 7. Usuario default: carlos.limon@nexusqtech.com / 00@Limonero (sysadmin)
INSERT INTO platform_users (username, display_name, password_hash, role, role_id)
VALUES (
    'carlos.limon@nexusqtech.com',
    'Carlos Limón',
    '$2b$12$uZDj1iVUhpcoJLzAr1/GFuqGLhYdijCIj3MR3QU3VlylsSDR8MMOe',
    'admin',
    (SELECT id FROM platform_roles WHERE name = 'sysadmin')
)
ON CONFLICT (username) DO UPDATE
    SET role_id = (SELECT id FROM platform_roles WHERE name = 'sysadmin'),
        display_name = 'Carlos Limón';

-- Dashboard por defecto para carlos.limon
INSERT INTO dashboards (user_id, title, is_default)
SELECT id, 'Mi Dashboard', true FROM platform_users WHERE username = 'carlos.limon@nexusqtech.com'
ON CONFLICT DO NOTHING;

-- ============================================================
-- NOTA: Una vez verificado que todo funciona, puedes:
--   ALTER TABLE platform_users ALTER COLUMN role_id SET NOT NULL;
--   ALTER TABLE platform_users DROP COLUMN IF EXISTS role;
-- ============================================================
