import os
import ssl
from fastapi import FastAPI, UploadFile, File, Form, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ssl._create_default_https_context = ssl._create_unverified_context

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = "sqlite:///./stats.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos do banco de dados
class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String)
    opponent = Column(String)
    location = Column(String)  # Casa ou Fora
    result = Column(String)    # Ex: 3x2
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    match_details = relationship("MatchDetail", back_populates="match")  # Relação com MatchDetail

class MatchDetail(Base):
    __tablename__ = "match_details"
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))  # Chave estrangeira para Match
    player_id = Column(Integer, ForeignKey("players.id"))  # Chave estrangeira para Player
    event_type = Column(String)  # Gol, Assistência, Cartão Amarelo, Cartão Vermelho
    minute = Column(Integer)
    notes = Column(String)
    
    match = relationship("Match", back_populates="match_details")  # Relação com Match
    player = relationship("Player")  # Relação com Player  

class Stats(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    player = relationship("Player")

class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)  # Nome do arquivo (não alterável)
    title = Column(String)     # Título do vídeo (editável)

Base.metadata.create_all(bind=engine)

# Função para obter a sessão do banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Configurar os templates Jinja2
templates = Jinja2Templates(directory="templates")

# Servir arquivos estáticos (para vídeos)
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

# Servir arquivos estáticos (para imagens)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Função para adicionar mensagens flash
def set_flash(response: RedirectResponse, message: str, category: str = "success"):
    response.set_cookie(key="flash_message", value=message)
    response.set_cookie(key="flash_category", value=category)

# Função para obter mensagens flash
def get_flash(request: Request):
    flash_message = request.cookies.get("flash_message", "")
    flash_category = request.cookies.get("flash_category", "")
    return flash_message, flash_category

# Rota principal que renderiza o template index.html
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    players = db.query(Player).all()
    stats = db.query(Stats).all()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "players": players,
        "stats": stats
    })

@app.post("/add_player/")
def add_player(request: Request, name: str = Form(...), position: str = Form(...), db: Session = Depends(get_db)):
    player = Player(name=name, position=position)
    db.add(player)
    db.commit()
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)

@app.post("/add_stats/")
def add_stats(request: Request, player_id: int = Form(...), goals: int = Form(...), assists: int = Form(...), db: Session = Depends(get_db)):
    stats = Stats(player_id=player_id, goals=goals, assists=assists)
    db.add(stats)
    db.commit()
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)

@app.post("/upload_video/")
def upload_video(request: Request, file: UploadFile = File(...), title: str = Form(...), db: Session = Depends(get_db)):
    file_location = f"videos/{file.filename}"
    os.makedirs("videos", exist_ok=True)
    with open(file_location, "wb") as f:
        f.write(file.file.read())

    # Salva o vídeo com o título fornecido
    video = Video(filename=file.filename, title=title)
    db.add(video)
    db.commit()

    response = RedirectResponse(url="/videos", status_code=303)
    set_flash(response, "Vídeo enviado com sucesso!", "success")
    return response

@app.get("/players", response_class=HTMLResponse)
def get_players(request: Request, db: Session = Depends(get_db)):
    players = db.query(Player).all()
    return templates.TemplateResponse("players.html", {"request": request, "players": players})

@app.get("/stats", response_class=HTMLResponse)
def get_stats(request: Request, db: Session = Depends(get_db)):
    stats = db.query(Stats).all()
    return templates.TemplateResponse("stats.html", {"request": request, "stats": stats})

@app.get("/videos", response_class=HTMLResponse)
def get_videos(request: Request, db: Session = Depends(get_db)):
    videos = db.query(Video).all()
    return templates.TemplateResponse("videos.html", {"request": request, "videos": videos})

@app.get("/calendar", response_class=HTMLResponse)
def get_calendar(request: Request, db: Session = Depends(get_db)):
    matches = db.query(Match).all()
    return templates.TemplateResponse("calendar.html", {"request": request, "matches": matches})

# Endpoint para excluir um jogador
@app.post("/delete_player/{player_id}")
def delete_player(request: Request, player_id: int, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if player:
        db.delete(player)
        db.commit()
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)

# Endpoint para excluir uma estatística
@app.post("/delete_stats/{stat_id}")
def delete_stats(request: Request, stat_id: int, db: Session = Depends(get_db)):
    stat = db.query(Stats).filter(Stats.id == stat_id).first()
    if stat:
        db.delete(stat)
        db.commit()
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)

# Endpoint para excluir um vídeo
@app.post("/delete_video/{video_id}")
def delete_video(request: Request, video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        # Remove o arquivo de vídeo do sistema de arquivos
        file_path = f"videos/{video.filename}"
        if os.path.exists(file_path):
            os.remove(file_path)
        db.delete(video)
        db.commit()
        response = RedirectResponse(url="/videos", status_code=303)
        set_flash(response, "Vídeo excluído com sucesso!", "success")
        return response
    else:
        response = RedirectResponse(url="/videos", status_code=303)
        set_flash(response, "Vídeo não encontrado.", "error")
        return response

# Endpoint para editar o título de um vídeo
@app.post("/edit_video/{video_id}")
def edit_video(request: Request, video_id: int, new_title: str = Form(...), db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        video.title = new_title  # Altera apenas o título
        db.commit()
        response = RedirectResponse(url="/videos", status_code=303)
        set_flash(response, "Título do vídeo atualizado com sucesso!", "success")
        return response
    else:
        response = RedirectResponse(url="/videos", status_code=303)
        set_flash(response, "Vídeo não encontrado.", "error")
        return response

# Endpoint para cadastrar calendário
#@app.post("/add_match/")
#def add_match(request: Request, date: str = Form(...), opponent: str = Form(...), db: Session = Depends(get_db)):
 #   match = Match(date=date, opponent=opponent)
 ##   db.add(match)
  #  db.commit()
   # return RedirectResponse(url="/calendar", status_code=303)

@app.post("/add_match/")
def add_match(
    request: Request,
    date: str = Form(...),
    opponent: str = Form(...),
    location: str = Form(...),
    db: Session = Depends(get_db)
):
    match = Match(date=date, opponent=opponent, location=location)
    db.add(match)
    db.commit()
    return RedirectResponse(url="/calendar", status_code=303)

@app.post("/add_match_detail/")
def add_match_detail(
    request: Request,
    match_id: int = Form(...),
    player_id: int = Form(...),
    event_type: str = Form(...),
    minute: int = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    detail = MatchDetail(
        match_id=match_id,
        player_id=player_id,
        event_type=event_type,
        minute=minute,
        notes=notes
    )
    db.add(detail)
    db.commit()
    return RedirectResponse(url=f"/match/{match_id}", status_code=303)

@app.get("/match/{match_id}", response_class=HTMLResponse)
def get_match_details(request: Request, match_id: int, db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    details = db.query(MatchDetail).filter(MatchDetail.match_id == match_id).all()
    players = db.query(Player).all()
    return templates.TemplateResponse("match_details.html", {
        "request": request,
        "match": match,
        "details": details,
        "players": players
    })