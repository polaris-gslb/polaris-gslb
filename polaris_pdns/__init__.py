#-*- coding: utf-8 -*-

from .core.polaris import Polaris

__all__ = [ 'main' ]

def main():
    Polaris().run()

