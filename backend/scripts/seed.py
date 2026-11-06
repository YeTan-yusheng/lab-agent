import argparse
import sys
from dataclasses import dataclass, field
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import BASE_DIR, settings
from app.core.password import hash_password
from app.core.permissions import Role, validate_roles
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.user import User, UserRoles

SEED_USERS = [
    ("student01", "学生一", ["student"]),
    ("teacher01", "教师一", ["teacher"]),
    ("admin01", "管理员一", ["admin"]),
    ("teacher_admin01", "教师管理员", ["teacher", "admin"]),
]

DEMO_LABS = [
    {
        "name": "计算机实验室",
        "location": "综合实验楼401",
        "capacity": 40,
        "open_time": "08:00",
        "close_time": "18:00",
        "description": "用于软件开发与算法实验",
        "status": 1,
    },
    {
        "name": "化学实验室",
        "location": "综合实验楼301",
        "capacity": 30,
        "open_time": "08:30",
        "close_time": "18:00",
        "description": "用于化学与材料实验",
        "status": 1,
    },
]

DEMO_EQUIPMENTS = {
    "计算机实验室": [
        {
            "name": "开发工作站",
            "description": "学生实验用工作站",
            "spec": "i7/32G/1T",
            "quantity": 10,
            "status": 1,
        },
        {
            "name": "网络交换机",
            "description": "网络实验设备",
            "spec": "48口",
            "quantity": 2,
            "status": 1,
        },
    ],
    "化学实验室": [
        {
            "name": "电子天平",
            "description": "精密称量",
            "spec": "0.0001g",
            "quantity": 2,
            "status": 1,
        },
        {
            "name": "通风橱",
            "description": "化学实验通风",
            "spec": "1.2m",
            "quantity": 2,
            "status": 1,
        },
    ],
}


@dataclass
class SeedUserResult:
    username: str
    user_created: bool = False
    password_reset: bool = False
    legacy_role_updated: bool = False
    roles_added: list[str] = field(default_factory=list)
    roles_removed: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(
            (
                self.user_created,
                self.password_reset,
                self.legacy_role_updated,
                self.roles_added,
                self.roles_removed,
            )
        )


@dataclass
class DemoSeedResult:
    labs_created: list[str] = field(default_factory=list)
    equipments_created: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.labs_created or self.equipments_created)


def seed_user(
    db: Session,
    username: str,
    name: str,
    roles: list[Role | str],
    password: str,
    reset: bool = False,
    dry_run: bool = False,
) -> SeedUserResult:
    profile = validate_roles(roles)
    user = db.scalar(select(User).where(User.username == username))
    result = SeedUserResult(username=username)

    if user is None:
        result.user_created = True
        existing_codes: set[str] = set()
        if not dry_run:
            user = User(
                username=username,
                password=hash_password(password),
                name=name,
                role=profile.primary_role.value,
                status=1,
                token_version=0,
            )
            db.add(user)
            db.flush()
    else:
        existing_codes = {
            row.role_code
            for row in db.scalars(
                select(UserRoles).where(UserRoles.user_id == user.id)
            )
        }
        if user.role != profile.primary_role.value:
            result.legacy_role_updated = True
            if not dry_run:
                user.role = profile.primary_role.value
        if reset:
            result.password_reset = True
            if not dry_run:
                user.password = hash_password(password)
                user.status = 1
                user.token_version += 1

    desired_codes = {role.value for role in profile.roles}
    result.roles_added = sorted(desired_codes - existing_codes)
    result.roles_removed = (
        sorted(existing_codes - desired_codes) if reset else []
    )

    if not dry_run:
        for role_code in result.roles_added:
            db.add(UserRoles(user_id=user.id, role_code=role_code))
        for role_code in result.roles_removed:
            row = db.scalar(
                select(UserRoles).where(
                    UserRoles.user_id == user.id,
                    UserRoles.role_code == role_code,
                )
            )
            if row:
                db.delete(row)
        db.flush()

    return result


def seed_demo_data(db: Session, dry_run: bool = False) -> DemoSeedResult:
    result = DemoSeedResult()

    for lab_spec in DEMO_LABS:
        lab_name = lab_spec["name"]
        lab = db.scalar(select(Lab).where(Lab.name == lab_name))

        if lab is None:
            result.labs_created.append(lab_name)
            if dry_run:
                result.equipments_created.extend(
                    f"{lab_name}/{item['name']}"
                    for item in DEMO_EQUIPMENTS.get(lab_name, [])
                )
                continue
            lab = Lab(**lab_spec)
            db.add(lab)
            db.flush()

        for equipment_spec in DEMO_EQUIPMENTS.get(lab_name, []):
            existing = db.scalar(
                select(Equipment).where(
                    Equipment.lab_id == lab.id,
                    Equipment.name == equipment_spec["name"],
                )
            )
            if existing is None:
                result.equipments_created.append(
                    f"{lab_name}/{equipment_spec['name']}"
                )
                if not dry_run:
                    db.add(Equipment(lab_id=lab.id, **equipment_spec))

    if not dry_run:
        db.flush()

    return result


def check_migration(db: Session) -> None:
    config = Config(str(BASE_DIR / "alembic.ini"))
    expected = ScriptDirectory.from_config(config).get_current_head()
    try:
        versions = set(
            db.execute(text("SELECT version_num FROM alembic_version")).scalars()
        )
    except Exception as exc:
        raise RuntimeError(
            "alembic_version 不存在，请先执行 alembic upgrade head"
        ) from exc
    if versions != {expected}:
        raise RuntimeError(
            f"数据库迁移版本 {sorted(versions)} 与 head {expected} 不一致，"
            "请先执行 alembic upgrade head"
        )


def mask_database_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def format_user_result(result: SeedUserResult, dry_run: bool) -> str:
    prefix = "[dry-run] " if dry_run else ""
    if not result.changed:
        return f"{prefix}skip user: {result.username}"

    actions: list[str] = []
    if result.user_created:
        actions.append("create user")
    if result.password_reset:
        actions.append("reset password")
    if result.legacy_role_updated:
        actions.append("update legacy role")
    if result.roles_added:
        actions.append("add roles: " + ", ".join(result.roles_added))
    if result.roles_removed:
        actions.append("remove roles: " + ", ".join(result.roles_removed))
    return f"{prefix}{result.username}: " + "; ".join(actions)


def format_demo_result(result: DemoSeedResult, dry_run: bool) -> str:
    prefix = "[dry-run] " if dry_run else ""
    if not result.changed:
        return f"{prefix}skip demo data: nothing to do"

    parts: list[str] = []
    if result.labs_created:
        parts.append("create labs: " + ", ".join(result.labs_created))
    if result.equipments_created:
        parts.append(
            "create equipments: " + ", ".join(result.equipments_created)
        )
    return f"{prefix}demo data: " + "; ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="初始化数据库-创建种子数据")
    parser.add_argument("--reset", action="store_true", help="重置种子账号密码")
    parser.add_argument(
        "--with-demo-data", action="store_true", help="同时创建实验室和设备"
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写数据库")
    parser.add_argument(
        "--force", action="store_true", help="非开发环境显式确认执行"
    )
    args = parser.parse_args(argv)

    if settings.app_env == "production" and not args.force:
        print(
            "APP_ENV=production，拒绝执行 seed；如确需执行请加 --force",
            file=sys.stderr,
        )
        return 2
    if settings.app_env not in ("development", "test") and not args.force:
        print(
            f"APP_ENV={settings.app_env} 不允许执行 seed；如确需执行请加 --force",
            file=sys.stderr,
        )
        return 2
    if not settings.test_database_url:
        print("TEST_DATABASE_URL 未配置", file=sys.stderr)
        return 2

    password = settings.seed_default_password
    if not password:
        if settings.app_env == "development":
            password = "123456"
            print(
                "WARNING: SEED_DEFAULT_PASSWORD 未配置，使用开发默认密码",
                file=sys.stderr,
            )
        else:
            print("SEED_DEFAULT_PASSWORD 未配置", file=sys.stderr)
            return 2

    print(f"target database: {mask_database_url(settings.test_database_url)}")

    try:
        engine = create_engine(settings.test_database_url)
    except Exception as exc:
        print(f"数据库连接配置错误: {exc}", file=sys.stderr)
        return 2

    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    user_results: list[SeedUserResult] = []
    demo_result = DemoSeedResult()

    try:
        with SessionLocal() as db:
            try:
                check_migration(db)
                for username, name, roles in SEED_USERS:
                    user_results.append(
                        seed_user(
                            db=db,
                            username=username,
                            name=name,
                            roles=roles,
                            password=password,
                            reset=args.reset,
                            dry_run=args.dry_run,
                        )
                    )
                if args.with_demo_data:
                    demo_result = seed_demo_data(db, dry_run=args.dry_run)

                if args.dry_run:
                    db.rollback()
                else:
                    db.commit()
            except Exception as exc:
                db.rollback()
                print(f"seed failed: {exc}", file=sys.stderr)
                return 1
    finally:
        engine.dispose()

    for result in user_results:
        print(format_user_result(result, args.dry_run))
    if args.with_demo_data:
        print(format_demo_result(demo_result, args.dry_run))

    if args.dry_run:
        print("dry-run complete, no changes written")
    else:
        print("seed complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())