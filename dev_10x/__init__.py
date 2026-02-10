try:
    from dev_10x.version import __version__
except ImportError:
    __version__ = '0.0.0+unknown'  # fallback for dev envs
