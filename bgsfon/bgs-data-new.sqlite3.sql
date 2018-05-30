BEGIN TRANSACTION;
DROP TABLE IF EXISTS `ticks`;
CREATE TABLE IF NOT EXISTS `ticks` (
	`timestamp`	INTEGER
);
DROP TABLE IF EXISTS `system_status`;
CREATE TABLE IF NOT EXISTS `system_status` (
	`date`	INTEGER,
	`system`	INTEGER,
	`controller_faction`	TEXT,
	`security`	TEXT,
	PRIMARY KEY(`date`,`system`)
);
DROP TABLE IF EXISTS `faction_state`;
CREATE TABLE IF NOT EXISTS `faction_state` (
	`date`	INTEGER,
	`state_name`	TEXT,
	`state_type`	TEXT,
	`faction_name`	TEXT,
	`trend`	INTEGER,
	PRIMARY KEY(`date`,`state_name`,`state_type`,`faction_name`)
);
DROP TABLE IF EXISTS `faction_system`;
CREATE TABLE IF NOT EXISTS `faction_system` (
	`date`	INTEGER,
	`name`	TEXT,
	`system`	TEXT,
	`influence`	REAL,
	PRIMARY KEY(`date`,`name`,`system`)
);
DROP TABLE IF EXISTS `Variables`;
CREATE TABLE IF NOT EXISTS `Variables` (
	`name`	INTEGER,
	`value`	INTEGER,
	PRIMARY KEY(`name`)
);
DROP TABLE IF EXISTS `Systems`;
CREATE TABLE IF NOT EXISTS `Systems` (
	`name`	TEXT,
	`population`	INTEGER,
	`economy`	TEXT,
	`distance`	REAL,
	`allegiance`	TEXT,
	`faction`	TEXT,
	`factionState`	TEXT,
	`x`	REAL,
	`y`	REAL,
	`z`	REAL,
	PRIMARY KEY(`name`)
);
DROP TABLE IF EXISTS `Stations`;
CREATE TABLE IF NOT EXISTS `Stations` (
	`system`	TEXT,
	`name`	TEXT,
	`type`	TEXT,
	`distance`	REAL,
	`economy`	TEXT,
	`controller`	TEXT,
	PRIMARY KEY(`system`,`name`)
);
DROP TABLE IF EXISTS `Factions`;
CREATE TABLE IF NOT EXISTS `Factions` (
	`faction_name`	TEXT UNIQUE,
	`allegiance`	TEXT,
	`government`	TEXT,
	`is_player`	INTEGER,
	`native_system`	TEXT,
	PRIMARY KEY(`faction_name`)
);
DROP TABLE IF EXISTS `Controlled_Systems`;
CREATE TABLE IF NOT EXISTS `Controlled_Systems` (
	`system_name`	TEXT,
	`active`	INTEGER
);
COMMIT;
