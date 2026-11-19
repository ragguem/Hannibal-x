-- Rôle de lecture du service doctrine (architecture 1.1.0 § 7) : SELECT sur le schéma v2, rien d'autre.
-- À passer par un administrateur ; le mot de passe est donné à l'exécution, jamais écrit ici :
--   psql "$ADMIN_URL" -v doctrine_password="$(cat /run/secrets/doctrine_db_password)" -f roles.sql
SELECT format('CREATE ROLE hannibal_doctrine LOGIN PASSWORD %L', :'doctrine_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hannibal_doctrine') \gexec

REVOKE ALL ON SCHEMA public FROM hannibal_doctrine;
GRANT USAGE ON SCHEMA v2 TO hannibal_doctrine;
GRANT SELECT ON ALL TABLES IN SCHEMA v2 TO hannibal_doctrine;
ALTER DEFAULT PRIVILEGES IN SCHEMA v2 GRANT SELECT ON TABLES TO hannibal_doctrine;
ALTER ROLE hannibal_doctrine SET default_transaction_read_only = on;
