CREATE TABLE IF NOT EXISTS magnet_link (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(64)  NOT NULL,
    thunder_url     VARCHAR(2048)     DEFAULT NULL,
    total_size_text VARCHAR(32)       DEFAULT NULL,
    group_name      VARCHAR(255)      DEFAULT NULL,
    title           VARCHAR(512)      DEFAULT NULL,
    miss_reason     VARCHAR(512)      DEFAULT NULL,
    start_date      DATE         NOT NULL,
    end_date        DATE         NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_code (code),
    KEY idx_dates (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
