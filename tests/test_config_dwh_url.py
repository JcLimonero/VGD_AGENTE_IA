from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agente_dwh.config import (
    ConfigError,
    REQUIRED_DWH_DATABASE_NAME,
    effective_dwh_url,
    postgres_database_name_from_url,
    prepare_dwh_url,
    validate_dwh_url_targets_vgd_prod,
)


class ConfigDwhUrlTests(unittest.TestCase):
    def test_parse_psycopg_url(self) -> None:
        self.assertEqual(
            postgres_database_name_from_url(
                "postgresql+psycopg://u:p@h:5432/vgd_dwh_prod_migracion"
            ),
            REQUIRED_DWH_DATABASE_NAME,
        )

    def test_parse_quoted_url(self) -> None:
        self.assertEqual(
            postgres_database_name_from_url(
                '"postgresql+psycopg://postgres:root@127.0.0.1:5432/vgd_dwh_prod_migracion"'
            ),
            REQUIRED_DWH_DATABASE_NAME,
        )

    def test_user_postgres_is_not_database_name(self) -> None:
        """Usuario «postgres» no debe confundirse con la base (make_url + path)."""
        self.assertEqual(
            postgres_database_name_from_url(
                "postgresql+psycopg://postgres:root@127.0.0.1:5432/vgd_dwh_prod_migracion"
            ),
            REQUIRED_DWH_DATABASE_NAME,
        )

    def test_validate_ok(self) -> None:
        validate_dwh_url_targets_vgd_prod(
            "postgresql://localhost:5432/vgd_dwh_prod_migracion"
        )

    def test_validate_ok_local_dwh_database(self) -> None:
        validate_dwh_url_targets_vgd_prod("postgresql://localhost:5432/dwh")

    def test_validate_wrong_db(self) -> None:
        with self.assertRaises(ConfigError):
            validate_dwh_url_targets_vgd_prod(
                "postgresql://localhost:5432/otra_base_interna"
            )

    def test_validate_postgres_db_is_coerced(self) -> None:
        validate_dwh_url_targets_vgd_prod("postgresql://localhost:5432/postgres")
        out = prepare_dwh_url("postgresql+psycopg://u:p@h:5432/postgres")
        self.assertIn(REQUIRED_DWH_DATABASE_NAME, out)
        self.assertIn("postgresql+psycopg://u:p@h:5432/", out)

    def test_prepare_missing_database_segment(self) -> None:
        out = prepare_dwh_url("postgresql+psycopg://postgres:root@127.0.0.1:5432")
        self.assertTrue(out.rstrip("/").endswith(REQUIRED_DWH_DATABASE_NAME))

    def test_effective_matches_prepare_when_not_skip(self) -> None:
        raw = "postgresql://localhost:5432/postgres"
        self.assertEqual(effective_dwh_url(raw), prepare_dwh_url(raw))

    @patch.dict(os.environ, {"AGENTE_DWH_SKIP_DB_NAME_CHECK": "1"}, clear=False)
    def test_validate_skip_allows_other_db(self) -> None:
        validate_dwh_url_targets_vgd_prod("postgresql://localhost:5432/postgres")


if __name__ == "__main__":
    unittest.main()
