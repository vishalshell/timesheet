from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import bcrypt
import jwt
from enum import Enum

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# JWT settings
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

class TimesheetStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"

class ProjectStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    username: str
    full_name: str
    role: UserRole
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

class UserCreate(BaseModel):
    email: str
    username: str
    full_name: str
    password: str
    role: UserRole = UserRole.EMPLOYEE

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    start_date: datetime
    end_date: Optional[datetime] = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    assigned_employees: List[str] = []
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ProjectCreate(BaseModel):
    name: str
    description: str
    start_date: datetime
    end_date: Optional[datetime] = None
    assigned_employees: List[str] = []

class Timesheet(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    project_id: str
    date: datetime
    hours: float
    description: str
    status: TimesheetStatus = TimesheetStatus.DRAFT
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TimesheetCreate(BaseModel):
    project_id: str
    date: datetime
    hours: float
    description: str

class TimesheetUpdate(BaseModel):
    hours: Optional[float] = None
    description: Optional[str] = None
    status: Optional[TimesheetStatus] = None

class TimesheetApproval(BaseModel):
    status: TimesheetStatus
    rejection_reason: Optional[str] = None

# Helper functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        
        user = await db.users.find_one({"username": username})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return User(**user)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(allowed_roles: List[UserRole]):
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Operation not permitted for your role"
            )
        return current_user
    return role_checker

# Authentication routes
@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"$or": [{"email": user_data.email}, {"username": user_data.username}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    user_dict = user_data.dict()
    user_dict.pop("password")
    user_obj = User(**user_dict)
    
    # Store user with hashed password
    user_to_store = user_obj.dict()
    user_to_store["password"] = hashed_password
    
    await db.users.insert_one(user_to_store)
    return user_obj

@api_router.post("/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    user = await db.users.find_one({"username": user_credentials.username})
    if not user or not verify_password(user_credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    user_obj = User(**user)
    return {"access_token": access_token, "token_type": "bearer", "user": user_obj}

@api_router.get("/auth/me", response_model=User)
async def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    return current_user

# Project routes
@api_router.post("/projects", response_model=Project)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    project_dict = project_data.dict()
    project_dict["created_by"] = current_user.id
    project_obj = Project(**project_dict)
    
    await db.projects.insert_one(project_obj.dict())
    return project_obj

@api_router.get("/projects", response_model=List[Project])
async def get_projects(current_user: User = Depends(get_current_active_user)):
    if current_user.role == UserRole.EMPLOYEE:
        # Employees can only see projects they're assigned to
        projects = await db.projects.find({"assigned_employees": current_user.id}).to_list(1000)
    else:
        # Managers and admins can see all projects
        projects = await db.projects.find().to_list(1000)
    
    return [Project(**project) for project in projects]

@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, current_user: User = Depends(get_current_active_user)):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_obj = Project(**project)
    
    # Check if employee has access to this project
    if current_user.role == UserRole.EMPLOYEE and current_user.id not in project_obj.assigned_employees:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return project_obj

@api_router.put("/projects/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    project_data: ProjectCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = project_data.dict()
    update_data["updated_at"] = datetime.utcnow()
    
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
    
    updated_project = await db.projects.find_one({"id": project_id})
    return Project(**updated_project)

@api_router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    result = await db.projects.delete_one({"id": project_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted successfully"}

# Timesheet routes
@api_router.post("/timesheets", response_model=Timesheet)
async def create_timesheet(
    timesheet_data: TimesheetCreate,
    current_user: User = Depends(get_current_active_user)
):
    # Check if project exists and user has access
    project = await db.projects.find_one({"id": timesheet_data.project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == UserRole.EMPLOYEE and current_user.id not in project["assigned_employees"]:
        raise HTTPException(status_code=403, detail="You are not assigned to this project")
    
    timesheet_dict = timesheet_data.dict()
    timesheet_dict["employee_id"] = current_user.id
    timesheet_obj = Timesheet(**timesheet_dict)
    
    await db.timesheets.insert_one(timesheet_obj.dict())
    return timesheet_obj

@api_router.get("/timesheets", response_model=List[Timesheet])
async def get_timesheets(
    project_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[TimesheetStatus] = None,
    current_user: User = Depends(get_current_active_user)
):
    query = {}
    
    if current_user.role == UserRole.EMPLOYEE:
        # Employees can only see their own timesheets
        query["employee_id"] = current_user.id
    elif employee_id:
        query["employee_id"] = employee_id
    
    if project_id:
        query["project_id"] = project_id
    
    if status:
        query["status"] = status
    
    timesheets = await db.timesheets.find(query).to_list(1000)
    return [Timesheet(**timesheet) for timesheet in timesheets]

@api_router.get("/timesheets/{timesheet_id}", response_model=Timesheet)
async def get_timesheet(timesheet_id: str, current_user: User = Depends(get_current_active_user)):
    timesheet = await db.timesheets.find_one({"id": timesheet_id})
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    
    timesheet_obj = Timesheet(**timesheet)
    
    # Check access permissions
    if current_user.role == UserRole.EMPLOYEE and timesheet_obj.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return timesheet_obj

@api_router.put("/timesheets/{timesheet_id}", response_model=Timesheet)
async def update_timesheet(
    timesheet_id: str,
    timesheet_data: TimesheetUpdate,
    current_user: User = Depends(get_current_active_user)
):
    timesheet = await db.timesheets.find_one({"id": timesheet_id})
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    
    timesheet_obj = Timesheet(**timesheet)
    
    # Check permissions
    if current_user.role == UserRole.EMPLOYEE:
        if timesheet_obj.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        if timesheet_obj.status in [TimesheetStatus.APPROVED, TimesheetStatus.REJECTED]:
            raise HTTPException(status_code=400, detail="Cannot edit approved/rejected timesheets")
    
    update_data = {k: v for k, v in timesheet_data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    # Handle status changes
    if "status" in update_data:
        if update_data["status"] == TimesheetStatus.SUBMITTED:
            update_data["submitted_at"] = datetime.utcnow()
    
    await db.timesheets.update_one({"id": timesheet_id}, {"$set": update_data})
    
    updated_timesheet = await db.timesheets.find_one({"id": timesheet_id})
    return Timesheet(**updated_timesheet)

@api_router.post("/timesheets/{timesheet_id}/approve", response_model=Timesheet)
async def approve_reject_timesheet(
    timesheet_id: str,
    approval_data: TimesheetApproval,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    timesheet = await db.timesheets.find_one({"id": timesheet_id})
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    
    if approval_data.status not in [TimesheetStatus.APPROVED, TimesheetStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="Invalid status for approval")
    
    update_data = {
        "status": approval_data.status,
        "updated_at": datetime.utcnow()
    }
    
    if approval_data.status == TimesheetStatus.APPROVED:
        update_data["approved_at"] = datetime.utcnow()
        update_data["approved_by"] = current_user.id
    else:
        update_data["rejected_at"] = datetime.utcnow()
        update_data["rejected_by"] = current_user.id
        update_data["rejection_reason"] = approval_data.rejection_reason
    
    await db.timesheets.update_one({"id": timesheet_id}, {"$set": update_data})
    
    updated_timesheet = await db.timesheets.find_one({"id": timesheet_id})
    return Timesheet(**updated_timesheet)

@api_router.delete("/timesheets/{timesheet_id}")
async def delete_timesheet(
    timesheet_id: str,
    current_user: User = Depends(get_current_active_user)
):
    timesheet = await db.timesheets.find_one({"id": timesheet_id})
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    
    timesheet_obj = Timesheet(**timesheet)
    
    # Check permissions
    if current_user.role == UserRole.EMPLOYEE:
        if timesheet_obj.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        if timesheet_obj.status in [TimesheetStatus.APPROVED, TimesheetStatus.REJECTED]:
            raise HTTPException(status_code=400, detail="Cannot delete approved/rejected timesheets")
    
    await db.timesheets.delete_one({"id": timesheet_id})
    return {"message": "Timesheet deleted successfully"}

# Dashboard routes
@api_router.get("/dashboard/summary")
async def get_dashboard_summary(current_user: User = Depends(get_current_active_user)):
    if current_user.role == UserRole.EMPLOYEE:
        # Employee dashboard - their own stats
        timesheets = await db.timesheets.find({"employee_id": current_user.id}).to_list(1000)
        projects = await db.projects.find({"assigned_employees": current_user.id}).to_list(1000)
        
        total_hours = sum(ts["hours"] for ts in timesheets)
        approved_hours = sum(ts["hours"] for ts in timesheets if ts["status"] == TimesheetStatus.APPROVED)
        pending_hours = sum(ts["hours"] for ts in timesheets if ts["status"] == TimesheetStatus.SUBMITTED)
        
        return {
            "total_hours": total_hours,
            "approved_hours": approved_hours,
            "pending_hours": pending_hours,
            "total_projects": len(projects),
            "total_timesheets": len(timesheets)
        }
    else:
        # Manager/Admin dashboard - all stats
        timesheets = await db.timesheets.find().to_list(1000)
        projects = await db.projects.find().to_list(1000)
        users = await db.users.find({"role": UserRole.EMPLOYEE}).to_list(1000)
        
        total_hours = sum(ts["hours"] for ts in timesheets)
        approved_hours = sum(ts["hours"] for ts in timesheets if ts["status"] == TimesheetStatus.APPROVED)
        pending_approvals = len([ts for ts in timesheets if ts["status"] == TimesheetStatus.SUBMITTED])
        
        return {
            "total_hours": total_hours,
            "approved_hours": approved_hours,
            "pending_approvals": pending_approvals,
            "total_projects": len(projects),
            "total_employees": len(users),
            "total_timesheets": len(timesheets)
        }

# Users management (for admins)
@api_router.get("/users", response_model=List[User])
async def get_users(current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MANAGER]))):
    users = await db.users.find().to_list(1000)
    return [User(**user) for user in users]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()