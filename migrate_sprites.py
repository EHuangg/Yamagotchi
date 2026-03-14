"""
Migrate sprites from nested structure to flat composited frame structure.

Source structure (assets/sprites/src/):
  src/idle/body/{skin}_bald.png + src/idle/jerseys/{jersey}.png
  src/madeShot/body/{skin}_bald.png + src/madeShot/jerseys/{jersey}.png + src/madeShot/ball.png
  src/block/body/block_{skin}.png
  src/missedShot/missedShot.png

Output structure (assets/sprites/frames/):
  frames/idle_{skin}_bald_{jersey}.png
  frames/madeshot_{skin}_bald_{jersey}.png
  frames/block_{skin}.png
  frames/missedshot.png
"""

import os
import shutil
import argparse
from PIL import Image

SPRITE_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'sprites')
SRC_DIR    = os.path.join(SPRITE_DIR, 'src')
FRAMES_DIR = os.path.join(SPRITE_DIR, 'frames')

FRAME_SIZE = 16
SKINS = ['dark', 'medium', 'light']
JERSEYS = [
    "celtics", "nets", "knicks", "76ers", "raptors", "bulls", "caveliers", "pistons", "pacers", "bucks",
    "hawks", "hornets", "heat", "magic", "wizards", "nuggets", "timberwolves", "thunder", "trailblazers",
    "jazz", "warriors", "clippers", "lakers", "suns", "kings", "mavericks", "rockets", "grizzlies",
    "pelicans", "spurs"
]

def composite_frames(body_img: Image.Image, jersey_img: Image.Image, ball_img: Image.Image = None) -> Image.Image:
    """
    Composite body + jersey + optional ball frame-by-frame.
    All inputs are horizontal spritesheets with FRAME_SIZE pixel frames.
    Returns composited spritesheet of the same format.
    """
    if body_img.width != jersey_img.width:
        raise ValueError(f"Body and jersey sheets must have same width: {body_img.width} vs {jersey_img.width}")

    num_frames = body_img.width // FRAME_SIZE
    result = Image.new('RGBA', (body_img.width, FRAME_SIZE))

    for i in range(num_frames):
        x = i * FRAME_SIZE
        body_frame   = body_img.crop((x, 0, x + FRAME_SIZE, FRAME_SIZE))
        jersey_frame = jersey_img.crop((x, 0, x + FRAME_SIZE, FRAME_SIZE))

        target = Image.new('RGBA', (FRAME_SIZE, FRAME_SIZE))
        target.paste(body_frame,   (0, 0), body_frame)
        target.paste(jersey_frame, (0, 0), jersey_frame)

        if ball_img:
            ball_frame = ball_img.crop((x, 0, x + FRAME_SIZE, FRAME_SIZE))
            target.paste(ball_frame, (0, 0), ball_frame)

        result.paste(target, (x, 0), target)

    return result


def migrate_idle():
    print("Migrating idle sprites...")
    idle_body_dir   = os.path.join(SRC_DIR, 'idle', 'body')
    idle_jersey_dir = os.path.join(SRC_DIR, 'idle', 'jerseys')

    for skin in SKINS:
        body_path = os.path.join(idle_body_dir, f'{skin}_bald.png')
        if not os.path.exists(body_path):
            print(f"  ⚠ Missing body: {body_path}")
            continue

        body_img = Image.open(body_path).convert('RGBA')

        for jersey in JERSEYS:
            jersey_path = os.path.join(idle_jersey_dir, f'{jersey}.png')
            if not os.path.exists(jersey_path):
                print(f"  ⚠ Missing jersey: {jersey_path}")
                continue

            jersey_img = Image.open(jersey_path).convert('RGBA')
            composited = composite_frames(body_img, jersey_img)
            composited.save(os.path.join(FRAMES_DIR, f'idle_{skin}_bald_{jersey}.png'))

    print("  ✓ Idle sprites composited")


def migrate_madeshot():
    print("Migrating madeShot sprites...")
    made_body_dir   = os.path.join(SRC_DIR, 'madeShot', 'body')
    made_jersey_dir = os.path.join(SRC_DIR, 'madeShot', 'jerseys')
    ball_path       = os.path.join(SRC_DIR, 'madeShot', 'ball.png')

    ball_img = None
    if os.path.exists(ball_path):
        ball_img = Image.open(ball_path).convert('RGBA')
    else:
        print(f"  ⚠ Missing ball: {ball_path}")

    for skin in SKINS:
        body_path = os.path.join(made_body_dir, f'{skin}_bald.png')
        if not os.path.exists(body_path):
            print(f"  ⚠ Missing body: {body_path}")
            continue

        body_img = Image.open(body_path).convert('RGBA')

        for jersey in JERSEYS:
            jersey_path = os.path.join(made_jersey_dir, f'{jersey}.png')
            if not os.path.exists(jersey_path):
                print(f"  ⚠ Missing jersey: {jersey_path}")
                continue

            jersey_img = Image.open(jersey_path).convert('RGBA')
            composited = composite_frames(body_img, jersey_img, ball_img)
            composited.save(os.path.join(FRAMES_DIR, f'madeshot_{skin}_bald_{jersey}.png'))

    print("  ✓ MadeShot sprites composited")


def migrate_block():
    print("Migrating block sprites...")
    block_body_dir = os.path.join(SRC_DIR, 'block', 'body')

    for skin in SKINS:
        src_path = os.path.join(block_body_dir, f'block_{skin}.png')
        if not os.path.exists(src_path):
            print(f"  ⚠ Missing block: {src_path}")
            continue
        shutil.copy(src_path, os.path.join(FRAMES_DIR, f'block_{skin}.png'))

    print("  ✓ Block sprites copied")


def migrate_missedshot():
    print("Migrating missedShot sprite...")
    src_path = os.path.join(SRC_DIR, 'missedShot', 'missedShot.png')

    if not os.path.exists(src_path):
        print(f"  ⚠ Missing missedShot: {src_path}")
        return

    shutil.copy(src_path, os.path.join(FRAMES_DIR, 'missedshot.png'))
    print("  ✓ MissedShot sprite copied")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', choices=['idle', 'madeshot', 'block', 'missedshot'],
                        help='Only migrate a specific animation type')
    parser.add_argument('--clean', action='store_true',
                        help='Wipe frames directory before migrating')
    args = parser.parse_args()

    os.makedirs(FRAMES_DIR, exist_ok=True)

    if args.clean:
        print(f"  Cleaning frames directory: {FRAMES_DIR}")
        shutil.rmtree(FRAMES_DIR)
        os.makedirs(FRAMES_DIR)

    print(f"[migrate_sprites] src:    {SRC_DIR}")
    print(f"[migrate_sprites] output: {FRAMES_DIR}")

    if args.only == 'idle' or not args.only:
        migrate_idle()
    if args.only == 'madeshot' or not args.only:
        migrate_madeshot()
    if args.only == 'block' or not args.only:
        migrate_block()
    if args.only == 'missedshot' or not args.only:
        migrate_missedshot()

    print("\n[migrate_sprites] Done!")
    if not args.only:
        total = len(SKINS) * len(JERSEYS) * 2 + len(SKINS) + 1
        print(f"  idle+madeshot : {len(SKINS) * len(JERSEYS) * 2}")
        print(f"  block         : {len(SKINS)}")
        print(f"  missedshot    : 1")
        print(f"  total         : {total}")

if __name__ == '__main__':
    main()