# Diem vao cho ban web (pygbag). tools/build_web.py chep file nay + src/ + assets/ vao build/web_app/
import asyncio
import os
import sys

import pygame  # noqa: F401  (pygbag chi tai cac goi duoc import truc tiep trong main.py)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import Finals  # noqa: E402


async def main():
    app = Finals.App()
    await app.run_async()


asyncio.run(main())
