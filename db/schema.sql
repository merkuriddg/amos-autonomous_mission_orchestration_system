-- AMOS — Autonomous Mission Orchestration System
-- Phase 1 Database Schema (MariaDB)
-- =====================================================

USE amos;

-- ─── USERS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    name            VARCHAR(100) NOT NULL DEFAULT '',
    role            VARCHAR(50)  NOT NULL DEFAULT 'observer',
    domain          VARCHAR(20)  NOT NULL DEFAULT 'all',
    access          JSON         NOT NULL,
    active          TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ─── ASSETS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assets (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    asset_id        VARCHAR(50)  NOT NULL UNIQUE,
    type            VARCHAR(50)  NOT NULL DEFAULT '',
    domain          VARCHAR(20)  NOT NULL DEFAULT 'ground',
    role            VARCHAR(50)  NOT NULL DEFAULT 'recon',
    autonomy_tier   TINYINT      NOT NULL DEFAULT 2,
    sensors         JSON         NOT NULL,
    weapons         JSON         NOT NULL,
    endurance_hr    DECIMAL(6,2) NOT NULL DEFAULT 0,
    lat             DECIMAL(10,6) NOT NULL DEFAULT 0,
    lng             DECIMAL(10,6) NOT NULL DEFAULT 0,
    alt_ft          DECIMAL(10,2) NOT NULL DEFAULT 0,
    integration     VARCHAR(30)  NOT NULL DEFAULT 'none',
    bridge_addr     VARCHAR(100) NOT NULL DEFAULT '',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_domain (domain)
) ENGINE=InnoDB;

-- ─── THREATS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS threats (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    threat_id       VARCHAR(50)  NOT NULL UNIQUE,
    type            VARCHAR(50)  NOT NULL DEFAULT '',
    lat             DECIMAL(10,6) DEFAULT NULL,
    lng             DECIMAL(10,6) DEFAULT NULL,
    speed_kts       INT          NOT NULL DEFAULT 0,
    neutralized     TINYINT(1)   NOT NULL DEFAULT 0,
    detected_by     JSON,
    first_detected  DATETIME     DEFAULT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_neutralized (neutralized)
) ENGINE=InnoDB;

-- ─── THEATERS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS theaters (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    theater_key     VARCHAR(50)  NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    lat             DECIMAL(10,6) NOT NULL DEFAULT 0,
    lng             DECIMAL(10,6) NOT NULL DEFAULT 0,
    ao_north        DECIMAL(10,6) DEFAULT NULL,
    ao_south        DECIMAL(10,6) DEFAULT NULL,
    ao_east         DECIMAL(10,6) DEFAULT NULL,
    ao_west         DECIMAL(10,6) DEFAULT NULL,
    zoom            INT          NOT NULL DEFAULT 10,
    description     TEXT,
    active          TINYINT(1)   NOT NULL DEFAULT 0,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ─── MISSIONS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS missions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'planned',
    created_by      VARCHAR(50)  NOT NULL,
    plan            JSON,
    started_at      DATETIME     DEFAULT NULL,
    completed_at    DATETIME     DEFAULT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- ─── MISSION EVENTS ──────────────────────────────────
CREATE TABLE IF NOT EXISTS mission_events (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    mission_id      INT          NOT NULL,
    event_type      VARCHAR(50)  NOT NULL,
    details         JSON,
    timestamp       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mission_events_mission
        FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE,
    INDEX idx_mission_id (mission_id)
) ENGINE=InnoDB;

-- ─── AUDIT LOG ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user            VARCHAR(50)  NOT NULL,
    action          VARCHAR(100) NOT NULL,
    target_type     VARCHAR(50)  DEFAULT NULL,
    target_id       VARCHAR(100) DEFAULT NULL,
    detail          JSON,
    ip              VARCHAR(45)  DEFAULT NULL,
    timestamp       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB;

-- ─── RECORDING FRAMES ────────────────────────────────
CREATE TABLE IF NOT EXISTS recording_sessions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(36)  NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL DEFAULT 'Untitled',
    started_by      VARCHAR(50)  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'recording',
    frame_count     INT          NOT NULL DEFAULT 0,
    started_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stopped_at      DATETIME     DEFAULT NULL,
    INDEX idx_status (status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS recording_frames (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(36)  NOT NULL,
    frame_seq       INT          NOT NULL,
    clock_elapsed   DECIMAL(12,1) NOT NULL,
    asset_state     JSON         NOT NULL,
    threat_state    JSON         NOT NULL,
    timestamp       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_seq (session_id, frame_seq),
    CONSTRAINT fk_recording_frames_session
        FOREIGN KEY (session_id) REFERENCES recording_sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─── CHAT MESSAGES (Phase 2) ─────────────────────────
CREATE TABLE IF NOT EXISTS chat_messages (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    channel         VARCHAR(64)  NOT NULL DEFAULT 'general',
    sender          VARCHAR(64)  NOT NULL,
    message         TEXT         NOT NULL,
    timestamp       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_channel_ts (channel, timestamp)
) ENGINE=InnoDB;

-- ─── ASSET LOCKS (Phase 2) ───────────────────────────
CREATE TABLE IF NOT EXISTS asset_locks (
    asset_id        VARCHAR(32)  PRIMARY KEY,
    locked_by       VARCHAR(64)  NOT NULL,
    locked_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP    NULL,
    INDEX idx_locked_by (locked_by)
) ENGINE=InnoDB;

-- ─── SYSTEM MAP NODES ────────────────────────────────
CREATE TABLE IF NOT EXISTS system_map_nodes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    node_key        VARCHAR(64)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    phase           VARCHAR(20)  NOT NULL DEFAULT 'left',
    critical        TINYINT(1)   NOT NULL DEFAULT 0,
    trails          JSON         NOT NULL,
    pos_x           DOUBLE       DEFAULT NULL,
    pos_y           DOUBLE       DEFAULT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ─── SYSTEM MAP EDGES ────────────────────────────────
CREATE TABLE IF NOT EXISTS system_map_edges (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    source_key      VARCHAR(64)  NOT NULL,
    target_key      VARCHAR(64)  NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_edge (source_key, target_key),
    INDEX idx_source (source_key),
    INDEX idx_target (target_key)
) ENGINE=InnoDB;
