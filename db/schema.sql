-- tmux-claude-sessions schema (MariaDB 11 / MySQL 8)
CREATE DATABASE IF NOT EXISTS claude_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE claude_db;

/*M!999999\- enable the sandbox mode */ 

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `tmux_sessions` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `sort_order` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'row order on the page (drag handle)',
  `session_name` varchar(64) NOT NULL COMMENT 'Claude / Remote Control session name',
  `project_path` varchar(255) NOT NULL COMMENT 'working dir of the session',
  `tmux_alias` varchar(64) NOT NULL COMMENT 'tmux session name',
  `start_on_boot` tinyint(1) NOT NULL DEFAULT 0,
  `desired_state` enum('running','stopped') NOT NULL DEFAULT 'stopped' COMMENT 'set by the web page',
  `actual_state` enum('running','stopped','starting','stopping','error') NOT NULL DEFAULT 'stopped' COMMENT 'set by tmux-claude-sessions',
  `rss_mb` int(10) unsigned DEFAULT NULL,
  `claude_version` varchar(32) DEFAULT NULL,
  `update_requested` tinyint(1) NOT NULL DEFAULT 0,
  `last_seen` datetime DEFAULT NULL,
  `last_error` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `session_name` (`session_name`),
  UNIQUE KEY `tmux_alias` (`tmux_alias`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `host_stats` (
  `host` varchar(64) NOT NULL,
  `cpu_pct` decimal(5,1) NOT NULL,
  `mem_used_mb` int(10) unsigned NOT NULL,
  `mem_total_mb` int(10) unsigned NOT NULL,
  `swap_used_mb` int(10) unsigned NOT NULL DEFAULT 0,
  `claude_latest` varchar(32) DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`host`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='live load of the machines, written by tmux-claude-sessions';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

