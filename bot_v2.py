#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

import weatherbot as _weatherbot


if __name__ == "__main__":
    _weatherbot.main(runtime=_weatherbot)
else:
    sys.modules[__name__] = _weatherbot
