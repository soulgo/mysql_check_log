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

 Date: 07/04/2025 15:30:30
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for mysql_servers
-- ----------------------------
DROP TABLE IF EXISTS `mysql_servers`;
CREATE TABLE `mysql_servers`  (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `server_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '服务器名称',
  `server_ip` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '服务器IP',
  `last_scan_time` datetime NULL DEFAULT NULL COMMENT '最后扫描时间',
  `config_id` int(11) NOT NULL COMMENT '配置文件中的ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_server_ip`(`server_ip`) USING BTREE,
  INDEX `idx_config_id`(`config_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for user_activities
-- ----------------------------
DROP TABLE IF EXISTS `user_activities`;
CREATE TABLE `user_activities`  (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '操作用户',
  `operation_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '操作类型',
  `operation_detail` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '操作详情',
  `timestamp` datetime NOT NULL COMMENT '操作时间',
  `client_ip` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '客户端IP',
  `server_id` int(11) NULL DEFAULT NULL,
  `risk_level` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT 'LOW',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `server_id`(`server_id`) USING BTREE,
  INDEX `idx_timestamp`(`timestamp`) USING BTREE,
  INDEX `idx_user_name`(`user_name`) USING BTREE,
  INDEX `idx_operation_type`(`operation_type`) USING BTREE,
  CONSTRAINT `user_activities_ibfk_1` FOREIGN KEY (`server_id`) REFERENCES `mysql_servers` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 3506 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
