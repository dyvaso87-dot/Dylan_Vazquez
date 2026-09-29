import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Laptop


class LaptopCreate(BaseModel):
    marca: str
    modelo: str
    ram_gb: int


class LaptopOut(BaseModel):
    id: int
    marca: str
    modelo: str
    ram_gb: int
    disponible: bool

    model_config = {"from_attributes": True}


def esperar_mysql(intentos: int = 30, pausa: float = 2.0):
    """MySQL puede tardar en aceptar conexiones: reintenta antes de fallar."""
    for _ in range(intentos):
        try:
            with engine.connect():
                return
        except OperationalError:
            time.sleep(pausa)
    raise RuntimeError("MySQL no respondió a tiempo")


def carga_inicial():
    with SessionLocal() as db:
        if db.query(Laptop).count() == 0:
            db.add_all([
                Laptop(marca="Dell", modelo="Latitude 5440", ram_gb=16, disponible=True),
                Laptop(marca="Lenovo", modelo="ThinkPad E14", ram_gb=8, disponible=False),
                Laptop(marca="HP", modelo="ProBook 450", ram_gb=16, disponible=True),
            ])
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    esperar_mysql()
    Base.metadata.create_all(bind=engine)
    carga_inicial()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def raiz():
    return {"mensaje": "API del laboratorio de cómputo"}


@app.get("/laptops", response_model=list[LaptopOut])
def listar_laptops(db: Session = Depends(get_db)):
    return db.query(Laptop).order_by(Laptop.id).all()


# Debe ir ANTES de /laptops/{laptop_id}, o "disponibles" se interpretaría como un id
@app.get("/laptops/disponibles", response_model=list[LaptopOut])
def listar_disponibles(db: Session = Depends(get_db)):
    return (
        db.query(Laptop)
        .filter(Laptop.disponible == True)  # noqa: E712
        .order_by(Laptop.id)
        .all()
    )


@app.get("/laptops/{laptop_id}", response_model=LaptopOut)
def obtener_laptop(laptop_id: int, db: Session = Depends(get_db)):
    laptop = db.get(Laptop, laptop_id)
    if laptop is None:
        raise HTTPException(status_code=404, detail="Laptop no encontrada")
    return laptop


@app.post("/laptops", response_model=LaptopOut, status_code=201)
def crear_laptop(datos: LaptopCreate, db: Session = Depends(get_db)):
    laptop = Laptop(marca=datos.marca, modelo=datos.modelo, ram_gb=datos.ram_gb, disponible=True)
    db.add(laptop)
    db.commit()
    db.refresh(laptop)
    return laptop
