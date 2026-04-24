import os
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from .database import Base, engine, get_db
from .models import User, Project, UserProject, Calculation
from .auth import (
    SESSION_SECRET, MATERIALS, ROUND_MATERIALS,
    hash_password, verify_password, generate_password,
    get_current_user, require_user, require_admin,
    compute_weight_kg,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Steel Weight System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 24 * 7)


def _ensure_seed():
    db = next(get_db())
    try:
        if db.query(User).filter(User.role == "admin").count() == 0:
            db.add(User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                first_login=True,
            ))
            db.commit()
            print("[seed] Created default admin (admin/admin123)")
    finally:
        db.close()


_ensure_seed()


# ---------- Pydantic schemas ----------
class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    new_password: str


class CreateUserIn(BaseModel):
    username: str
    role: str


class UpdateRoleIn(BaseModel):
    role: str


class ProjectIn(BaseModel):
    name: str
    description: str = ""


class AssignIn(BaseModel):
    user_id: int


class CalcIn(BaseModel):
    material: str
    length: float
    qty: int
    width: Optional[float] = None
    thickness: Optional[float] = None
    diameter: Optional[float] = None


# ---------- Helpers ----------
def _project_accessible(db: Session, user: User, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role != "admin":
        ok = db.query(UserProject).filter(
            UserProject.user_id == user.id, UserProject.project_id == project_id
        ).first()
        if not ok:
            raise HTTPException(status_code=403, detail="Not assigned to this project")
    return project


def _user_dict(u: User):
    return {
        "id": u.id, "username": u.username, "role": u.role,
        "firstLogin": u.first_login,
        "createdAt": u.created_at.isoformat(),
    }


def _project_dict(p: Project):
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "createdAt": p.created_at.isoformat(),
    }


def _calc_dict(c: Calculation, username: str | None = None):
    return {
        "id": c.id, "projectId": c.project_id, "userId": c.user_id,
        "username": username or (c.user.username if c.user else ""),
        "material": c.material,
        "length": c.length, "width": c.width, "thickness": c.thickness,
        "diameter": c.diameter, "qty": c.qty,
        "weightKg": c.weight_kg, "weightTonnes": c.weight_tonnes,
        "createdAt": c.created_at.isoformat(),
    }


# ---------- Meta ----------
@app.get("/api/meta")
def meta():
    return {
        "materials": MATERIALS,
        "roundMaterials": list(ROUND_MATERIALS),
        "density": 7850,
    }


# ---------- Auth ----------
@app.post("/api/login")
def api_login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == body.username).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    request.session["user_id"] = u.id
    return _user_dict(u)


@app.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def api_me(request: Request, db: Session = Depends(get_db)):
    u = get_current_user(request, db)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _user_dict(u)


@app.post("/api/change-password")
def api_change_password(body: ChangePasswordIn, request: Request, db: Session = Depends(get_db)):
    u = require_user(request, db)
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    u.password_hash = hash_password(body.new_password)
    u.first_login = False
    db.commit()
    return _user_dict(u)


# ---------- Admin: Users ----------
@app.get("/api/admin/users")
def list_users(request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    out = []
    for u in db.query(User).order_by(User.created_at.desc()).all():
        cnt = db.query(func.count(UserProject.project_id)).filter(UserProject.user_id == u.id).scalar() or 0
        d = _user_dict(u); d["assignedProjects"] = cnt
        out.append(d)
    return out


@app.post("/api/admin/users")
def create_user(body: CreateUserIn, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    if body.role not in ("admin", "user", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    pw = generate_password()
    nu = User(username=username, password_hash=hash_password(pw), role=body.role, first_login=True)
    db.add(nu); db.commit(); db.refresh(nu)
    return {"user": _user_dict(nu), "generatedPassword": pw}


@app.patch("/api/admin/users/{user_id}/role")
def update_role(user_id: int, body: UpdateRoleIn, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    if body.role not in ("admin", "user", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.role = body.role; db.commit()
    return _user_dict(u)


@app.post("/api/admin/users/{user_id}/reset-password")
def reset_password(user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    pw = generate_password()
    u.password_hash = hash_password(pw); u.first_login = True
    db.commit()
    return {"user": _user_dict(u), "generatedPassword": pw}


@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    me = require_admin(require_user(request, db))
    if user_id == me.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(u); db.commit()
    return {"ok": True}


# ---------- Admin: Projects ----------
@app.get("/api/admin/projects")
def admin_list_projects(request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    out = []
    for p in db.query(Project).order_by(Project.created_at.desc()).all():
        users = db.query(func.count(UserProject.user_id)).filter(UserProject.project_id == p.id).scalar() or 0
        ent = db.query(func.count(Calculation.id)).filter(Calculation.project_id == p.id).scalar() or 0
        kg = db.query(func.coalesce(func.sum(Calculation.weight_kg), 0)).filter(Calculation.project_id == p.id).scalar() or 0
        d = _project_dict(p)
        d.update({"assignedUsers": users, "entries": ent, "weightKg": float(kg)})
        out.append(d)
    return out


@app.post("/api/admin/projects")
def admin_create_project(body: ProjectIn, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name required")
    p = Project(name=body.name.strip(), description=body.description.strip())
    db.add(p); db.commit(); db.refresh(p)
    return _project_dict(p)


@app.patch("/api/admin/projects/{project_id}")
def admin_update_project(project_id: int, body: ProjectIn, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    p.name = body.name.strip(); p.description = body.description.strip()
    db.commit()
    return _project_dict(p)


@app.delete("/api/admin/projects/{project_id}")
def admin_delete_project(project_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(p); db.commit()
    return {"ok": True}


@app.get("/api/admin/projects/{project_id}/assignments")
def admin_get_assignments(project_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    assigned_ids = {a.user_id for a in db.query(UserProject).filter(UserProject.project_id == project_id).all()}
    all_users = db.query(User).order_by(User.username).all()
    return {
        "project": _project_dict(p),
        "assigned": [_user_dict(u) for u in all_users if u.id in assigned_ids],
        "available": [_user_dict(u) for u in all_users if u.id not in assigned_ids and u.role != "admin"],
    }


@app.post("/api/admin/projects/{project_id}/assignments")
def admin_assign(project_id: int, body: AssignIn, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    if not db.query(User).filter(User.id == body.user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    if not db.query(UserProject).filter(
        UserProject.project_id == project_id, UserProject.user_id == body.user_id
    ).first():
        db.add(UserProject(project_id=project_id, user_id=body.user_id))
        db.commit()
    return {"ok": True}


@app.delete("/api/admin/projects/{project_id}/assignments/{user_id}")
def admin_unassign(project_id: int, user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    db.query(UserProject).filter(
        UserProject.project_id == project_id, UserProject.user_id == user_id
    ).delete()
    db.commit()
    return {"ok": True}


# ---------- Admin: Dashboard ----------
@app.get("/api/admin/dashboard")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    require_admin(require_user(request, db))
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_projects = db.query(func.count(Project.id)).scalar() or 0
    total_calcs = db.query(func.count(Calculation.id)).scalar() or 0
    total_kg = db.query(func.coalesce(func.sum(Calculation.weight_kg), 0)).scalar() or 0
    by_role = {"admin": 0, "user": 0, "viewer": 0}
    for role, cnt in db.query(User.role, func.count(User.id)).group_by(User.role).all():
        by_role[role] = cnt
    rows = (
        db.query(Project.id, Project.name,
                 func.coalesce(func.sum(Calculation.weight_kg), 0).label("kg"),
                 func.count(Calculation.id).label("entries"))
        .outerjoin(Calculation, Calculation.project_id == Project.id)
        .group_by(Project.id, Project.name)
        .order_by(desc("kg")).limit(5).all()
    )
    top = [{"id": pid, "name": n, "weightKg": float(kg), "entries": ent} for pid, n, kg, ent in rows]
    recent = db.query(Calculation).order_by(desc(Calculation.created_at)).limit(8).all()
    return {
        "totals": {
            "users": total_users, "projects": total_projects,
            "calculations": total_calcs, "weightKg": float(total_kg),
        },
        "byRole": by_role, "topProjects": top,
        "recent": [_calc_dict(c) for c in recent],
    }


# ---------- User: Projects & Calculations ----------
@app.get("/api/projects")
def list_projects(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if user.role == "admin":
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
    else:
        projects = (
            db.query(Project).join(UserProject, UserProject.project_id == Project.id)
            .filter(UserProject.user_id == user.id)
            .order_by(Project.created_at.desc()).all()
        )
    out = []
    for p in projects:
        kg = db.query(func.coalesce(func.sum(Calculation.weight_kg), 0)).filter(Calculation.project_id == p.id).scalar() or 0
        ent = db.query(func.count(Calculation.id)).filter(Calculation.project_id == p.id).scalar() or 0
        d = _project_dict(p); d.update({"weightKg": float(kg), "entries": ent})
        out.append(d)
    return out


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    project = _project_accessible(db, user, project_id)
    calcs = (
        db.query(Calculation).filter(Calculation.project_id == project_id)
        .order_by(Calculation.created_at.desc()).all()
    )
    total_kg = sum(c.weight_kg for c in calcs)
    return {
        "project": _project_dict(project),
        "calculations": [_calc_dict(c) for c in calcs],
        "totalKg": total_kg,
        "canEdit": user.role != "viewer",
    }


@app.post("/api/projects/{project_id}/calculations")
def add_calc(project_id: int, body: CalcIn, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot submit calculations")
    _project_accessible(db, user, project_id)
    if body.material not in MATERIALS:
        raise HTTPException(status_code=400, detail="Invalid material")
    if body.length <= 0 or body.qty <= 0:
        raise HTTPException(status_code=400, detail="Length and quantity must be positive")
    kg = compute_weight_kg(body.material, body.length, body.qty,
                           body.width, body.thickness, body.diameter)
    c = Calculation(
        project_id=project_id, user_id=user.id, material=body.material,
        length=body.length, width=body.width, thickness=body.thickness,
        diameter=body.diameter, qty=body.qty,
        weight_kg=kg, weight_tonnes=kg / 1000,
    )
    db.add(c); db.commit(); db.refresh(c)
    return _calc_dict(c, user.username)


@app.delete("/api/projects/{project_id}/calculations/{calc_id}")
def delete_calc(project_id: int, calc_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    _project_accessible(db, user, project_id)
    c = db.query(Calculation).filter(Calculation.id == calc_id, Calculation.project_id == project_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Calculation not found")
    if user.role != "admin" and c.user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot delete other users' entries")
    db.delete(c); db.commit()
    return {"ok": True}


@app.get("/api/projects/{project_id}/dashboard")
def project_dashboard(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    project = _project_accessible(db, user, project_id)
    rows = (
        db.query(Calculation.material,
                 func.coalesce(func.sum(Calculation.weight_kg), 0),
                 func.count(Calculation.id))
        .filter(Calculation.project_id == project_id)
        .group_by(Calculation.material).all()
    )
    by_material = [{"material": m, "weightKg": float(kg), "entries": cnt} for m, kg, cnt in rows]
    ts = (
        db.query(Calculation.created_at, Calculation.weight_kg)
        .filter(Calculation.project_id == project_id)
        .order_by(Calculation.created_at.asc()).all()
    )
    bucket = defaultdict(lambda: {"kg": 0.0, "entries": 0})
    for ca, kg in ts:
        d = ca.date().isoformat()
        bucket[d]["kg"] += float(kg); bucket[d]["entries"] += 1
    timeline = [{"date": d, "weightKg": v["kg"], "entries": v["entries"]} for d, v in sorted(bucket.items())]
    return {
        "project": _project_dict(project),
        "byMaterial": by_material,
        "timeline": timeline,
        "totalKg": sum(b["weightKg"] for b in by_material),
        "totalEntries": sum(b["entries"] for b in by_material),
    }


# ---------- Static HTML site ----------
@app.get("/")
def root_redirect():
    return RedirectResponse("/login.html", status_code=302)



