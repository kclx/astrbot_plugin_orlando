## 1️⃣ 冒险者表（adventurer）

```sql
CREATE TABLE adventurer (
    id            VARCHAR(36) PRIMARY KEY COMMENT '冒险者唯一ID，UUID',
    name          VARCHAR(36) NOT NULL COMMENT '冒险者名称',
    status        ENUM('IDLE', 'WORKING', 'REST', 'QUIT') DEFAULT 'IDLE' COMMENT '当前状态：IDLE=空闲, WORKING=执行任务, REST=休息, QUIT=退出',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) COMMENT='冒险者表，记录所有冒险者及其当前状态';
```

---

## 2️⃣ 委托任务表（quest）

```sql
CREATE TABLE quest (
    id              VARCHAR(36) PRIMARY KEY COMMENT '委托唯一ID，UUID',
    title           VARCHAR(100) NOT NULL COMMENT '任务标题',
    description     TEXT COMMENT '任务描述',
    reward          DECIMAL(10,2) NOT NULL COMMENT '任务报酬',
    deadline        DATETIME COMMENT '任务截止时间',
    status          ENUM('PUBLISHED', 'ASSIGNED', 'COMPLETED', 'TIMEOUT') DEFAULT 'PUBLISHED' COMMENT '任务状态：PUBLISHED=已发布, ASSIGNED=已接取, COMPLETED=已完成, TIMEOUT=超时未完成',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) COMMENT='委托任务表，记录任务信息及状态';
```

---

## 3️⃣ 冒险者任务分配表（quest_assign）

```sql
CREATE TABLE quest_assign (
    id            VARCHAR(36) PRIMARY KEY COMMENT '分配记录ID，UUID',
    quest_id      VARCHAR(36) NOT NULL COMMENT '关联任务ID',
    adventurer_id VARCHAR(36) NOT NULL COMMENT '关联冒险者ID',
    assign_time   DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '任务接取时间',
    finish_time   DATETIME COMMENT '任务完成时间',
    status        ENUM('ONGOING', 'FINISHED', 'FORCED_END', 'TIMEOUT', 'CHECK_FINISHED') DEFAULT 'ONGOING' COMMENT '任务分配状态：ONGOING=执行中, FINISHED=完成, FORCED_END=强制终止, TIMEOUT=超时, CHECK_FINISHED=确认完成',

    CONSTRAINT uq_adventurer_quest UNIQUE(adventurer_id, status) COMMENT '保证冒险者同一时刻只能接一个正在进行的任务',

    FOREIGN KEY (quest_id) REFERENCES quest(id) ON DELETE CASCADE,
    FOREIGN KEY (adventurer_id) REFERENCES adventurer(id) ON DELETE CASCADE
) COMMENT='冒险者任务分配表，记录冒险者接取任务及进度';
```

> 注：`uq_adventurer_quest` 唯一约束确保冒险者不能同时接多个 `ONGOING` 任务，可以在业务逻辑中判断状态。

---

## 4️⃣ 任务材料表（quest_material）

```sql
CREATE TABLE quest_material (
    id              VARCHAR(36) PRIMARY KEY COMMENT '材料ID，UUID',
    quest_assign_id VARCHAR(36) NOT NULL COMMENT '关联任务分配记录ID',
    material_name   VARCHAR(100) NOT NULL COMMENT '材料名称',
    amount          INT DEFAULT 1 COMMENT '材料数量',

    FOREIGN KEY (quest_assign_id) REFERENCES quest_assign(id) ON DELETE CASCADE
) COMMENT='任务材料表，记录冒险者提交的任务材料';
```

---

## 5️⃣ 系统日志表（system_log）

```sql
CREATE TABLE system_log (
    id            VARCHAR(36) PRIMARY KEY COMMENT '日志ID，UUID',
    event         VARCHAR(100) NOT NULL COMMENT '事件类型，例如：发布任务、接取任务、完成任务、更换冒险者等',
    detail        TEXT COMMENT '事件详细描述，可存储JSON或文字信息',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '事件发生时间'
) COMMENT='系统操作日志表，记录任务系统各类操作';
```
