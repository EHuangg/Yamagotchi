from PIL import Image, ImageDraw

FRAME_SIZE = 32
NUM_FRAMES = 12
colors = [
    (100, 180, 255),  # idle 0
    (110, 190, 255),  # idle 1
    (120, 200, 255),  # idle 2
    (255, 220, 50),   # scoring 0
    (255, 200, 30),   # scoring 1
    (255, 180, 10),   # scoring 2
    (50, 200, 120),   # passing
    (180, 100, 255),  # rebounding
    (255, 100, 100),  # blocking
    (100, 255, 180),  # stealing
    (150, 150, 150),  # missed
    (200, 100, 60),   # turnover
]

sheet = Image.new("RGBA", (FRAME_SIZE * NUM_FRAMES, FRAME_SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(sheet)

for i, color in enumerate(colors):
    x = i * FRAME_SIZE
    # Body
    draw.rectangle([x+10, 8, x+22, 24], fill=color)
    # Head
    draw.ellipse([x+11, 2, x+21, 12], fill=color)
    # Legs
    draw.rectangle([x+10, 24, x+15, 30], fill=color)
    draw.rectangle([x+17, 24, x+22, 30], fill=color)

sheet.save("assets/sprites/player.png")
print("Saved placeholder sprite sheet to assets/sprites/player.png")