# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AI Music Agent server.

Usage:
    pyinstaller server.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Project root
ROOT = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(ROOT, 'api', 'run.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Include prompt templates and other data files
        (os.path.join(ROOT, 'src', 'agent', 'prompts.py'), os.path.join('src', 'agent')),
    ],
    hiddenimports=[
        'api',
        'api.app',
        'api.routes',
        'api.routes.generate',
        'api.routes.tasks',
        'api.routes.chat',
        'api.routes.files',
        'api.routes.mv',
        'api.routes.recommendations',
        'api.routes.chat_history',
        'api.services',
        'api.services.auto_save',
        'api.services.chat_service',
        'api.services.mv_pipeline',
        'api.services.mv_store',
        'api.services.recommendation_service',
        'api.services.storyboard',
        'api.services.task_recovery',
        'api.services.task_store',
        'src',
        'src.config',
        'src.logger',
        'src.agent',
        'src.agent.agent',
        'src.agent.prompts',
        'src.clients',
        'src.clients.gemini',
        'src.clients.gemini_image',
        'src.clients.suno',
        'src.clients.veo',
        'src.clients.vertex_auth',
        'src.tools',
        'src.tools.base',
        'src.tools.music',
        'flask',
        'flask_cors',
        'dotenv',
        'requests',
        'json',
        'logging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='server',
)
