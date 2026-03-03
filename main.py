from fastapi import FastAPI, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String, DateTime, func, select, update, delete
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
import uvicorn

from database import Base, get_db, create_tables


app = FastAPI()

@app.on_event("startup")
async def startup():
    await create_tables()


class UsersModel(Base):
    
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    age = Column(Integer, nullable=False, index=True)
    country = Column(String, nullable=False, index=True)
    
    created_at = Column(DateTime, server_default=func.now())
    
    
class UserBase(BaseModel):
    pass


class UserCreate(UserBase):
    
    name: str = Field(..., min_length=2, max_length=30, description="User name")
    age: int = Field(..., ge=18, description="User age")
    country: str = Field(..., description="User country")
    

class UserUpdate(BaseModel):
    
    name: Optional[str] = None
    age: Optional[int] = None
    country: Optional[str] = None
    

class UserResponse(BaseModel):
    
    id: int = Field(...)
    name: str
    age: int
    country: str
    created_at: datetime
    
    
    class Config:
        from_attributes = True
    

class UsersListResponse(BaseModel):
    
    users_list: list[UserResponse]
    total: int
    
    
class UsersNameAgeResponse(BaseModel):
    
    name: str
    age: int
    

class UsersNameCountryResponse(BaseModel):
    
    name: str
    country: str
    
    

class UserCrud:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    
    async def get_users(self) -> List[UsersModel]:
        
        stmt = select(UsersModel)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    
    async def get_user_by_id(self, id: int) -> Optional[UsersModel]:
        
        stmt = select(UsersModel).where(UsersModel.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    
    async def get_user_by_name(self, name: str) -> Optional[UsersModel]:
        
        stmt = select(UsersModel).where(UsersModel.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    
    async def get_users_list_by_age(self, age: int) -> list[UsersNameAgeResponse]:
        
        stmt = select(UsersModel.name, UsersModel.age).where(UsersModel.age == age)
        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [UsersNameAgeResponse(**row) for row in rows]
    

    async def get_users_list_by_country(self, country: str) -> list[UsersNameCountryResponse]:
        
        stmt = select(UsersModel.name, UsersModel.country).where(UsersModel.country == country)
        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [UsersNameCountryResponse(**row) for row in rows]
    
    
    async def user_create(self, user_data: UserCreate) -> UsersModel:
        
        new_user = UsersModel(**user_data.model_dump())
        
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user
    
    
    async def user_update(self, id: int, user_data_update: UserUpdate) -> Optional[UsersModel]:
        
        stmt = update(UsersModel).where(UsersModel.id == id).values(**user_data_update.model_dump(exclude_none=True)).returning(UsersModel)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one_or_none()
    
    
    async def user_delete(self, id: int) -> UsersModel | None:
        
        stmt = delete(UsersModel).where(UsersModel.id == id).returning(UsersModel)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one_or_none()
    
    
class UsersService:
    
    def __init__(self, db: AsyncSession):
        self.users_crud = UserCrud(db)
        
    
    async def get_all_users(self) -> UsersListResponse:
        
        all_users = await self.users_crud.get_users()
        
        model_users = [UserResponse.model_validate(user) for user in all_users]
        
        return UsersListResponse(users_list=model_users, total=len(model_users))
    
    
    async def get_user_by_id(self, user_id: int) -> UserResponse:
        
        user = await self.users_crud.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        return UserResponse.model_validate(user)
    
    
    async def get_user_by_name(self, user_name: str) -> UserResponse:
        
        user = await self.users_crud.get_user_by_name(user_name)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        return UserResponse.model_validate(user)
            
    
    async def get_users_list_by_age(self, age: int) -> List[UsersNameAgeResponse]:
        
        users = await self.users_crud.get_users_list_by_age(age)
            
        return [UsersNameAgeResponse.model_validate(user) for user in users]
    
    
    async def get_users_list_by_country(self, country: str) -> List[UsersNameCountryResponse]:
        
        users = await self.users_crud.get_users_list_by_country(country)
        
        return [UsersNameCountryResponse.model_validate(user) for user in users]
    
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        
        new_user = await self.users_crud.user_create(user_data)
        
        return UserResponse.model_validate(new_user)
    
    
    async def update_user(self, id: int, user_data: UserUpdate) -> UserResponse:
        
        current_user = await self.users_crud.user_update(id, user_data)
        
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Current user not found"
            )
            
        return UserResponse.model_validate(current_user)
    
    
    async def delete_user(self, id: int) -> UserResponse:
        
        user = await self.users_crud.user_delete(id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or already deleted"
            )
            
        return UserResponse.model_validate(user)
    

@app.get("/")
async def greet():
    
    return {"status": "200"}
    
    
@app.get("/users", response_model=UsersListResponse)
async def get_users(db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    users = await service.get_all_users()
    
    return users


@app.get("/users/name-age", response_model=list[UsersNameAgeResponse])
async def get_users_list_by_age(age: int, db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    user_age = await service.get_users_list_by_age(age)
    
    return user_age


@app.get("/users/name-country", response_model=list[UsersNameCountryResponse])
async def get_users_list_country(country: str, db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    user_country = await service.get_users_list_by_country(country)
    
    return user_country


@app.post("/users/create", response_model=UserResponse)
async def create_user(data_user: UserCreate, db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    new_user = await service.create_user(data_user)
    
    return new_user


@app.get("/users/{id}", response_model=UserResponse)
async def get_user_by_id(id: int, db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    user_id = await service.get_user_by_id(id)
    
    return user_id


@app.get("/users/by-name/{name}", response_model=UserResponse)
async def get_user_by_name(name: str, db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    user_name = await service.get_user_by_name(name)
    
    return user_name


@app.put("/users/update/{id}", response_model=UserResponse)
async def update_user(id: int, data_user: UserUpdate, db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    user_put = await service.update_user(id, data_user)
    
    return user_put


@app.delete("/users/delete/{id}", response_model=UserResponse)
async def delete_user(id: int, db: AsyncSession = Depends(get_db)):
    
    service = UsersService(db)
    
    deleted_user = await service.delete_user(id)
    
    return deleted_user


if __name__ == '__main__':
    uvicorn.run("main:app", reload=True)