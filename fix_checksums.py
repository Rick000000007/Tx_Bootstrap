import re
import glob

# pkg-config
with open('recipes/pkg-config.recipe', 'r') as f:
    content = f.read()
content = re.sub(
    r'https://pkgconfig.freedesktop.org/releases/pkg-config-0.29.2.tar.gz.*',
    'https://pkgconfig.freedesktop.org/releases/pkg-config-0.29.2.tar.gz    6fc69c01688c9458a57eb9a1664c9aba372ccda420a02bf4429fe610e7e7d591',
    content
)
with open('recipes/pkg-config.recipe', 'w') as f:
    f.write(content)

# m4
with open('recipes/m4.recipe', 'r') as f:
    content = f.read()
content = re.sub(
    r'https://mirrors.kernel.org/gnu/m4/m4-1.4.19.tar.gz.*',
    'https://mirrors.kernel.org/gnu/m4/m4-1.4.19.tar.xz    63aede5c6d33b6d9b13511cd0be2cac046f2e70fd0a07aa9573a04a82783af96',
    content
)
with open('recipes/m4.recipe', 'w') as f:
    f.write(content)

