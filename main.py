import pygame, math, random
from pathlib import Path

pygame.init()
W,H,FPS=960,540,60
screen=pygame.display.set_mode((W,H))
pygame.display.set_caption("Ретро-FPS — Гвинтівка")
clock=pygame.time.Clock()
ROOT=Path(__file__).parent
FONT=pygame.font.Font(None,28)
BIG=pygame.font.Font(None,78)
FOV=1.05; RAYS=320; MAXD=18
COLORS={"1":(105,105,115),"2":(130,80,55),"3":(65,100,115),"4":(125,65,110)}

def load_img(path,size=None,alpha=True):
    try:
        s=pygame.image.load(str(ROOT/"textures"/path))
        s=s.convert_alpha() if alpha else s.convert()
        return pygame.transform.scale(s,size) if size else s
    except (pygame.error,FileNotFoundError): return None

def load_sound(path):
    try:return pygame.mixer.Sound(str(ROOT/"sounds"/path))
    except (pygame.error,FileNotFoundError):return None

class Enemy:
    def __init__(self,x,y,boss=False):
        self.x,self.y=x,y
        self.boss=boss
        self.maxhp=300 if boss else 70
        self.hp=self.maxhp
        self.speed=.48 if boss else .75
        self.cool=random.uniform(.2,.8)
        self.dead=False
        self.hurt=0
    def update(self,p,world,dt):
        if self.dead:return
        self.cool=max(0,self.cool-dt);self.hurt=max(0,self.hurt-dt)
        dx,dy=p.x-self.x,p.y-self.y;d=math.hypot(dx,dy)
        if .85<d<10:
            vx,vy=dx/d*self.speed*dt,dy/d*self.speed*dt
            if not world.blocked(self.x+vx,self.y):self.x+=vx
            if not world.blocked(self.x,self.y+vy):self.y+=vy
        if d<(6 if self.boss else 4) and self.cool<=0:
            visible=True
            for i in range(1,15):
                t=i/15
                if world.wall(self.x+dx*t,self.y+dy*t):visible=False;break
            if visible:
                p.hurt(16 if self.boss else 7)
                self.cool=1.0 if self.boss else 1.35
    def damage(self,n):
        if self.dead:return
        self.hp-=n;self.hurt=.12
        if self.hp<=0:self.hp=0;self.dead=True

class World:
    def load(self,n):
        lines=[x.rstrip() for x in (ROOT/f"levels/level{n}.txt").read_text(encoding="utf-8").splitlines() if x.strip()]
        self.grid=[];self.enemies=[];self.pickups=[];self.doors=[];self.boss=None;self.exit=None
        self.h=len(lines);self.w=max(map(len,lines))
        for y,line in enumerate(lines):
            row=list(line.ljust(self.w,"1"))
            for x,c in enumerate(row):
                pos=(x+.5,y+.5)
                if c=="P":self.start=pos;row[x]="0"
                elif c=="E":self.enemies.append(Enemy(*pos));row[x]="0"
                elif c=="B":self.boss=Enemy(*pos,True);row[x]="0"
                elif c=="X":self.exit=pos;row[x]="0"
                elif c in "AH":self.pickups.append({"p":pos,"kind":c,"taken":False});row[x]="0"
                elif c=="D":self.doors.append({"x":x,"y":y,"open":False});row[x]="0"
            self.grid.append(row)
    def wall(self,x,y):
        ix,iy=int(x),int(y)
        if ix<0 or iy<0 or ix>=self.w or iy>=self.h:return True
        if self.grid[iy][ix]!="0":return True
        return any(d["x"]==ix and d["y"]==iy and not d["open"] for d in self.doors)
    def wall_type(self,x,y):
        ix,iy=int(x),int(y)
        if 0<=ix<self.w and 0<=iy<self.h and self.grid[iy][ix] in COLORS:return self.grid[iy][ix]
        return "1"
    def blocked(self,x,y,r=.18):
        return any(self.wall(a,b) for a,b in [(x-r,y),(x+r,y),(x,y-r),(x,y+r),(x-r,y-r),(x+r,y+r)])
    def near_door(self,x,y):
        ds=[d for d in self.doors if not d["open"] and (x-d["x"]-.5)**2+(y-d["y"]-.5)**2<1.5**2]
        return min(ds,key=lambda d:(x-d["x"]-.5)**2+(y-d["y"]-.5)**2) if ds else None

class Player:
    def __init__(self,x,y):
        self.x,self.y=x,y;self.a=0;self.hp=100;self.ammo=40;self.weapon="rifle"
        self.cool=0;self.anim=0;self.flash=0;self.kills=0
    def hurt(self,n):self.hp=max(0,self.hp-n);self.flash=.15
    def update(self,dt,world,keys,mouse_dx):
        self.a+=mouse_dx*.0025+(int(keys[pygame.K_RIGHT])-int(keys[pygame.K_LEFT]))*2.2*dt
        f=int(keys[pygame.K_w])-int(keys[pygame.K_s]);s=int(keys[pygame.K_d])-int(keys[pygame.K_a])
        length=math.hypot(f,s) or 1;f/=length;s/=length
        dx=(math.cos(self.a)*f+math.cos(self.a+math.pi/2)*s)*3*dt
        dy=(math.sin(self.a)*f+math.sin(self.a+math.pi/2)*s)*3*dt
        if not world.blocked(self.x+dx,self.y):self.x+=dx
        if not world.blocked(self.x,self.y+dy):self.y+=dy
        self.cool=max(0,self.cool-dt);self.anim=max(0,self.anim-dt);self.flash=max(0,self.flash-dt)
    def attack(self):
        if self.cool>0:return False
        if self.ammo<=0:return False
        self.ammo-=1;self.cool=.22;self.anim=.14
        return True

class Game:
    def __init__(self):
        self.state="menu";self.level=1;self.world=World();self.running=True
        self.menu_bg=load_img("menu/background.png",(W,H),False);self.logo=load_img("menu/logo.png")
        self.walltex={i:load_img(f"walls/wall{i}.png") for i in range(1,5)}
        self.sky=load_img("sky/sky.png",(W,H//2),False);self.floor=load_img("floor/ground.png",(W,H//2),False)
        self.enemytex=load_img("enemies/enemy.png");self.bosstex=load_img("enemies/boss.png")
        self.weaptex={"rifle":[load_img(f"weapons/rifle_{i}.png") for i in range(1,4)]}
        self.shoot_sound=load_sound("shoot.wav")
    def start(self,n):
        self.level=n;self.world.load(n);self.p=Player(*self.world.start)
        self.enemies=self.world.enemies[:]+([self.world.boss] if self.world.boss else [])
        self.msg="ЗНИЩ УСІХ ВОРОГІВ І БОСА"
        self.msgtime=2.0;self.state="game"
        pygame.mouse.set_visible(False);pygame.event.set_grab(True)
    def attack(self):
        if not self.p.attack():return
        if self.shoot_sound:self.shoot_sound.play()
        target=None;best=99
        for e in self.enemies:
            if e.dead:continue
            dx,dy=e.x-self.p.x,e.y-self.p.y;d=math.hypot(dx,dy)
            angle=math.atan2(dy,dx);delta=(angle-self.p.a+math.pi)%(2*math.pi)-math.pi
            if abs(delta)>.16 or d>9 or d>=best:continue
            if any(self.world.wall(self.p.x+dx*i/20,self.p.y+dy*i/20) for i in range(1,20)):continue
            target=e;best=d
        if target:
            was=target.dead;target.damage(38)
            if target.dead and not was:self.p.kills+=1
    def events(self):
        for e in pygame.event.get():
            if e.type==pygame.QUIT:self.running=False
            elif self.state=="menu":
                if e.type==pygame.KEYDOWN and e.key==pygame.K_RETURN:self.start(1)
                elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                    if W//2-145<e.pos[0]<W//2+145 and 260<e.pos[1]<330:self.start(1)
                    elif W//2-145<e.pos[0]<W//2+145 and 345<e.pos[1]<415:self.running=False
            elif self.state=="game":
                if e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_ESCAPE:self.state="pause";pygame.mouse.set_visible(True);pygame.event.set_grab(False)
                    elif e.key==pygame.K_e:
                        d=self.world.near_door(self.p.x,self.p.y)
                        if d:d["open"]=True;self.msg="ДВЕРІ ВІДЧИНЕНО";self.msgtime=1
                    elif e.key in (pygame.K_SPACE,pygame.K_f):self.attack()
                elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:self.attack()
            elif self.state=="pause" and e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE:self.state="game";pygame.mouse.set_visible(False);pygame.event.set_grab(True)
                elif e.key==pygame.K_m:self.state="menu";pygame.mouse.set_visible(True);pygame.event.set_grab(False)
            elif self.state in ("dead","victory") and e.type==pygame.KEYDOWN and e.key==pygame.K_RETURN:
                self.state="menu";pygame.mouse.set_visible(True);pygame.event.set_grab(False)
    def update(self,dt):
        if self.state!="game":return
        keys=pygame.key.get_pressed();mdx=pygame.mouse.get_rel()[0] if pygame.mouse.get_focused() else 0
        self.p.update(dt,self.world,keys,mdx)
        for e in self.enemies:e.update(self.p,self.world,dt)
        # Перемога одразу після знищення всіх звичайних ворогів і боса.
        if self.enemies and all(e.dead for e in self.enemies):
            self.state="victory"
            pygame.mouse.set_visible(True)
            pygame.event.set_grab(False)
            return
        for it in self.world.pickups:
            if it["taken"]:continue
            x,y=it["p"]
            if (self.p.x-x)**2+(self.p.y-y)**2<.4**2:
                if it["kind"]=="H" and self.p.hp<100:self.p.hp=min(100,self.p.hp+30);it["taken"]=True
                elif it["kind"]=="A":self.p.ammo+=15;it["taken"]=True
        self.msgtime=max(0,self.msgtime-dt)
        if self.p.hp<=0:self.state="dead";pygame.mouse.set_visible(True);pygame.event.set_grab(False);return
        if self.world.exit and (self.p.x-self.world.exit[0])**2+(self.p.y-self.world.exit[1])**2<.4**2:
            if all(e.dead for e in self.enemies):
                self.state="victory";pygame.mouse.set_visible(True);pygame.event.set_grab(False)
            else:self.msg="СПОЧАТКУ ЗНИЩ УСІХ ВОРОГІВ";self.msgtime=1
    def render_world(self):
        if self.sky:screen.blit(self.sky,(0,0))
        else:screen.fill((28,35,53))
        if self.floor:screen.blit(self.floor,(0,H//2))
        else:pygame.draw.rect(screen,(48,43,39),(0,H//2,W,H//2))
        depth=[MAXD]*RAYS;step=FOV/RAYS;colw=W/RAYS
        for r in range(RAYS):
            a=self.p.a-FOV/2+r*step;ca,sa=math.cos(a),math.sin(a);d=.025
            while d<MAXD:
                x,y=self.p.x+ca*d,self.p.y+sa*d
                if self.world.wall(x,y):break
                d+=.025
            if d>=MAXD:continue
            d=max(.001,d*math.cos(a-self.p.a));depth[r]=d
            wh=min(int(H/d),H*3);top=H//2-wh//2;wt=self.world.wall_type(x,y);tex=self.walltex.get(int(wt))
            if tex:
                tx=int(((y%1) if abs(x-round(x))<abs(y-round(y)) else (x%1))*tex.get_width())
                strip=pygame.transform.scale(tex.subsurface((max(0,min(tex.get_width()-1,tx)),0,1,tex.get_height())),(int(colw)+1,wh))
                screen.blit(strip,(int(r*colw),top))
            else:
                shade=max(.2,1-d/MAXD);base=COLORS[wt]
                pygame.draw.rect(screen,tuple(int(c*shade) for c in base),(int(r*colw),top,int(colw)+1,wh))
        self.depth=depth
    def render_sprites(self):
        for e in sorted([e for e in self.enemies if not e.dead],key=lambda e:math.hypot(e.x-self.p.x,e.y-self.p.y),reverse=True):
            dx,dy=e.x-self.p.x,e.y-self.p.y;dist=math.hypot(dx,dy)
            delta=(math.atan2(dy,dx)-self.p.a+math.pi)%(2*math.pi)-math.pi
            if abs(delta)>FOV*.7:continue
            corrected=dist*math.cos(delta)
            if corrected<=.1:continue
            ri=max(0,min(RAYS-1,int((delta+FOV/2)/FOV*RAYS)))
            if corrected>self.depth[ri]+.2:continue
            size=min(int(H/corrected*(1.4 if e.boss else .85)),H*2)
            sx=W//2+int(math.tan(delta)/math.tan(FOV/2)*(W//2))
            rect=pygame.Rect(sx-size//3,H//2-size//2,size*2//3,size)
            tex=self.bosstex if e.boss else self.enemytex
            if tex:screen.blit(pygame.transform.scale(tex,rect.size),rect)
            else:
                pygame.draw.rect(screen,(130,35,150) if e.boss else ((255,100,80) if e.hurt else (155,48,48)),rect)
                ey=rect.y+size//3
                pygame.draw.rect(screen,(255,220,80),(sx-size//10,ey,max(3,size//12),max(3,size//12)))
                pygame.draw.rect(screen,(255,220,80),(sx+size//20,ey,max(3,size//12),max(3,size//12)))
            if e.boss:
                pygame.draw.rect(screen,(45,20,20),(W//2-120,15,240,15))
                pygame.draw.rect(screen,(190,35,45),(W//2-120,15,int(240*e.hp/e.maxhp),15))
    def render_weapon(self):
        frames=self.weaptex[self.p.weapon];frame=0 if self.p.anim<=0 else (1 if self.p.anim>.08 else 2)
        tex=frames[frame]
        if tex:screen.blit(tex,(W//2-tex.get_width()//2,H-tex.get_height()));return
        cx,by=W//2,H-12
        if self.p.weapon=="rifle":
            pygame.draw.rect(screen,(48,48,52),(cx-32,by-120,64,120));pygame.draw.rect(screen,(100,100,105),(cx-10,by-200,20,100))
            if self.p.anim:pygame.draw.polygon(screen,(255,190,60),[(cx,by-230),(cx-22,by-190),(cx,by-202),(cx+22,by-190)])
    def text(self,s,font,y,color=(240,240,240)):
        surf=font.render(s,True,color);screen.blit(surf,(W//2-surf.get_width()//2,y))
    def draw(self):
        if self.state=="menu":
            if self.menu_bg:screen.blit(self.menu_bg,(0,0))
            else:screen.fill((18,20,30))
            if self.logo:screen.blit(self.logo,(W//2-self.logo.get_width()//2,80))
            else:self.text("РЕТРО-FPS",BIG,95)
            for y,label in [(260,"ПОЧАТИ ГРУ"),(345,"ВИХІД")]:
                pygame.draw.rect(screen,(42,42,48),(W//2-145,y,290,58));pygame.draw.rect(screen,(180,180,190),(W//2-145,y,290,58),2);self.text(label,FONT,y+17)
            self.text("WASD — рух | Миша — огляд | ЛКМ / ПРОБІЛ / F — стріляти",FONT,450)
        elif self.state=="game":
            self.render_world();self.render_sprites();self.render_weapon()
            pygame.draw.rect(screen,(12,12,15),(0,H-34,W,34))
            info=f"ЗДОРОВ’Я {self.p.hp}   НАБОЇ {self.p.ammo}   ГВИНТІВКА   ВОРОГИ {self.p.kills}"
            screen.blit(FONT.render(info,True,(240,240,240)),(12,H-29))
            pygame.draw.line(screen,(240,240,240),(W//2-7,H//2),(W//2+7,H//2),2);pygame.draw.line(screen,(240,240,240),(W//2,H//2-7),(W//2,H//2+7),2)
            if self.p.flash:
                ov=pygame.Surface((W,H),pygame.SRCALPHA);ov.fill((180,0,0,65));screen.blit(ov,(0,0))
            if self.msgtime>0:self.text(self.msg,FONT,H//2+60,(255,235,140))
        else:
            screen.fill((12,13,18))
            title={"pause":"ПАУЗА","dead":"ТИ ЗАГИНУВ","victory":"ПЕРЕМОГА!"}[self.state]
            sub={"pause":"ESC — продовжити | M — головне меню","dead":"Натисни ENTER, щоб повернутися в меню","victory":"Усіх ворогів знищено! Натисни ENTER для меню"}[self.state]
            self.text(title,BIG,190);self.text(sub,FONT,285)

game=Game()
while game.running:
    dt=min(clock.tick(FPS)/1000,.04)
    game.events();game.update(dt);game.draw();pygame.display.flip()
pygame.quit()
