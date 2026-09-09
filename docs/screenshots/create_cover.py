"""Render original FrameKind cover artwork. Requires Pillow; no external assets."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SCALE = 2
SIZE = (1500, 1000)
PAPER = '#f6f4ec'
INK = '#252b29'
ACCENT = '#b44b30'
MUTED = '#6b7364'
image = Image.new('RGB', (SIZE[0] * SCALE, SIZE[1] * SCALE), PAPER)
draw = ImageDraw.Draw(image)
fonts = Path('/System/Library/Fonts/Supplemental')

def font(name, size):
    return ImageFont.truetype(str(fonts / name), int(size * SCALE))

def text(x, y, value, size=20, fill=INK, face='Arial.ttf'):
    draw.text((x * SCALE, y * SCALE), value, fill=fill, font=font(face, size))

def rect(box, fill, outline=None, width=1):
    draw.rectangle(tuple(int(v * SCALE) for v in box), fill=fill, outline=outline, width=int(width * SCALE))

def line(points, fill, width=1):
    draw.line([(int(x * SCALE), int(y * SCALE)) for x, y in points], fill=fill, width=int(width * SCALE), joint='curve')

def poly(points, fill):
    draw.polygon([(int(x * SCALE), int(y * SCALE)) for x, y in points], fill=fill)

def circle(box, fill, outline=None, width=1):
    draw.ellipse(tuple(int(v * SCALE) for v in box), fill=fill, outline=outline, width=int(width * SCALE))

# A quiet editorial masthead.
for points in [[(112,91),(88,91),(88,115)],[(146,91),(170,91),(170,115)],[(170,149),(170,173),(146,173)],[(112,173),(88,173),(88,149)]]:
    line(points, ACCENT, 5)
poly([(121,113),(148,131),(121,150)], ACCENT)
text(194, 99, 'FrameKind', 52, face='Arial Bold.ttf')
text(198, 159, 'EVERY PART OF THE STORY.', 11, fill=MUTED)
text(1050, 113, 'THE ACCESSIBILITY', 16, fill=MUTED)
text(1050, 138, 'REVIEW ROOM', 16, fill=MUTED)
line([(88,216),(1412,216)], '#dcded0', 1)

# Main typographic lock-up.
text(87, 300, 'Every part', 100, face='Georgia.ttf')
text(87, 421, 'of the', 100, face='Georgia.ttf')
text(87, 535, 'story.', 119, fill=ACCENT, face='Georgia Italic.ttf')
text(94, 718, 'Accessibility review for film.', 24, fill=MUTED)
text(94, 760, 'Picture. Sound. Words.', 17, fill=MUTED)

# Original room illustration, drawn directly as geometric shapes.
ox, oy, k = 735, 294, 1.01

def point(x, y):
    return (ox + k*x, oy + k*y)

def scene_rect(box, fill, outline=None, width=1):
    x1, y1 = point(box[0], box[1]); x2, y2 = point(box[2], box[3])
    rect((x1,y1,x2,y2),fill,outline,width)

def scene_poly(points, fill):
    poly([point(x,y) for x,y in points],fill)

def scene_line(points, fill, width=1):
    line([point(x,y) for x,y in points],fill,width)

def scene_circle(box, fill, outline=None, width=1):
    x1,y1=point(box[0],box[1]); x2,y2=point(box[2],box[3])
    circle((x1,y1,x2,y2),fill,outline,width)

text(738, 267, 'FRAMEKIND / A MOMENT IN THE CUT', 11, fill=MUTED)
scene_rect((-10,-10,660,450),'#e8e7dc','#d9dccd',1)
scene_rect((0,0,650,440),'#1d2b2b')
scene_rect((0,300,650,440),'#233331')
scene_line([(0,301),(650,301)],'#4c5d50',1)
scene_rect((425,76,542,310),'#101b1c')
scene_rect((431,81,534,306),'#d4ad77')
scene_poly([(443,90),(504,98),(504,308),(443,307)],'#536055')
scene_circle((488,203,494,209),'#e3be7d')
scene_poly([(505,308),(532,307),(650,440),(456,440)],'#384136')
scene_rect((96,88,255,196),'#4a5852')
scene_rect((103,95,248,189),'#162124')
scene_poly([(104,181),(141,129),(177,162),(221,116),(248,149),(248,187),(104,187)],'#50675e')
scene_circle((200,102,230,132),'#c49a63')
scene_poly([(152,292),(323,292),(312,305),(139,305)],'#9a7960')
scene_line([(149,304),(149,386)],'#5a4937',8)
scene_line([(310,304),(310,386)],'#5a4937',8)
scene_poly([(179,284),(238,279),(238,285),(179,290)],'#d1bd8f')
scene_line([(277,278),(277,238)],'#778273',3)
scene_poly([(256,240),(267,214),(286,214),(299,240)],'#be9660')
scene_circle((260,280,292,288),'#756854')
scene_circle((354,189,392,227),'#0c1719')
scene_poly([(344,328),(342,280),(348,240),(359,227),(383,227),(397,245),(403,282),(395,329)],'#0c1719')
text(752, 311, '00:00:18:04', 10, fill='#b2beaa')

# The absent sound becomes a visible part of the picture.
scene_rect((64,344,631,409),'#101c1b')
scene_rect((58,338,625,403),'#fbf6e8')
scene_rect((58,338,62,403),ACCENT)
for x, h in [(83,8),(89,18),(95,26),(101,15),(107,7)]:
    scene_line([(x,370-h/2),(x,370+h/2)], ACCENT, 3)
text(ox + 125*k, oy + 354*k, '[a knock at the door]', 28, fill='#384632', face='Georgia.ttf')
scene_circle((579,357,607,385),'#fbf6e8','#b5bea6',1)
scene_line([(586,371),(600,371)],'#637951',2)
scene_line([(593,364),(593,378)],'#637951',2)
text(739, 763, 'The smallest sound can change the story.', 15, fill=MUTED, face='Georgia Italic.ttf')

# A modest footer, with no performance or compliance claims.
line([(88,872),(1412,872)], '#dcded0', 1)
text(90, 909, '01', 14, fill=ACCENT)
text(130, 907, 'Find the gap.', 18, fill=MUTED)
text(431, 909, '02', 14, fill=ACCENT)
text(471, 907, 'Review the evidence.', 18, fill=MUTED)
text(879, 909, '03', 14, fill=ACCENT)
text(919, 907, 'Make the edit.', 18, fill=MUTED)

image = image.resize(SIZE, Image.Resampling.LANCZOS)
target = ROOT / 'framekind-cover.png'
image.save(target, optimize=True)
print(f'{target}: {image.size[0]} x {image.size[1]}, {target.stat().st_size} bytes')
