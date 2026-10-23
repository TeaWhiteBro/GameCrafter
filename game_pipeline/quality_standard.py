"""Public quality policy; benchmark images must be explicit inputs."""


def default_benchmarks():
    # Public runs use the shared written quality contract. Explicit user-supplied
    # benchmark images remain supported; no previous case is required or mounted.
    return []
