/*
 Navicat Premium Dump SQL

 Source Server         : mysql5.7
 Source Server Type    : MySQL
 Source Server Version : 50736 (5.7.36-log)
 Source Host           : 192.168.10.129:3310
 Source Schema         : mysql_log

 Target Server Type    : MySQL
 Target Server Version : 50736 (5.7.36-log)
 File Encoding         : 65001

 Date: 09/04/2025 13:07:41
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for server_configs
-- ----------------------------
DROP TABLE IF EXISTS `server_configs`;
CREATE TABLE `server_configs`  (
  `server_id` int(11) NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `host` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `port` int(11) NULL DEFAULT 22,
  `user` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `ssh_key_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `general_log_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `binlog_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `enable_general_log` tinyint(1) NULL DEFAULT 1,
  `enable_binlog` tinyint(1) NULL DEFAULT 0,
  PRIMARY KEY (`server_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for server_scan_records
-- ----------------------------
DROP TABLE IF EXISTS `server_scan_records`;
CREATE TABLE `server_scan_records`  (
  `server_id` int(11) NOT NULL,
  `last_scan_time` datetime(6) NOT NULL,
  PRIMARY KEY (`server_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for server_scan_status
-- ----------------------------
DROP TABLE IF EXISTS `server_scan_status`;
CREATE TABLE `server_scan_status`  (
  `server_id` int(11) NOT NULL COMMENT '关联到 config.py 中 LOG_CONFIG 的服务器 ID',
  `last_scan_time` datetime(6) NULL DEFAULT NULL COMMENT '此服务器上次成功扫描完成的时间 (UTC)',
  PRIMARY KEY (`server_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '记录服务器扫描状态' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for system_settings
-- ----------------------------
DROP TABLE IF EXISTS `system_settings`;
CREATE TABLE `system_settings`  (
  `key` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `value` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`key`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for user_activities
-- ----------------------------
DROP TABLE IF EXISTS `user_activities`;
CREATE TABLE `user_activities`  (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '活动ID',
  `server_id` int(11) NOT NULL COMMENT '关联到 mysql_servers 表的 ID',
  `timestamp` datetime(6) NOT NULL COMMENT '活动发生时间(带微秒)',
  `user_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '数据库用户名',
  `client_host` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '客户端主机或IP',
  `db_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '操作的数据库名',
  `thread_id` int(11) NULL DEFAULT NULL COMMENT 'MySQL线程ID',
  `command_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '原始命令类型',
  `operation_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '解析后的操作类型',
  `argument` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '命令参数或SQL语句',
  `risk_level` enum('Low','Medium','High') CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT 'Low' COMMENT '风险等级',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_server_time`(`server_id`, `timestamp`) USING BTREE,
  INDEX `idx_user_time`(`user_name`, `timestamp`) USING BTREE,
  CONSTRAINT `user_activities_ibfk_1` FOREIGN KEY (`server_id`) REFERENCES `mysql_servers_old` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 1182 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '用户数据库活动记录' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
