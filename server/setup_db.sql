-- =============================================================================
-- PROJETO CARCARÁ — Script de inicialização do banco de dados
-- =============================================================================
-- Execute como superusuário PostgreSQL:
--   psql -U postgres -f setup_db.sql
-- =============================================================================
-- Cria usuário e banco
CREATE USER carcara_user WITH PASSWORD 'carcara_pass';
CREATE DATABASE carcara_db OWNER carcara_user;

-- Conecta ao banco e habilita PostGIS
\c carcara_db
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Concede privilégios
GRANT ALL PRIVILEGES ON DATABASE carcara_db TO carcara_user;
GRANT ALL ON SCHEMA public TO carcara_user;

-- As tabelas são criadas automaticamente pelo SQLAlchemy (init_db())
-- ao iniciar o servidor pela primeira vez.

-- =============================================================================
-- Verificação de instalação
-- =============================================================================
SELECT postgis_version();
