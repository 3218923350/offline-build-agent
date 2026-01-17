#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
离线构建 Agent - 命令行入口

使用方法:
    python -m offline_builder --input tools.json --output ./output

或:
    offline-build --input tools.json --output ./output
"""
from offline_builder.cli import main


if __name__ == "__main__":
    main()

