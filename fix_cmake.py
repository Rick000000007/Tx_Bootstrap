import re
with open('recipes/cmake.recipe', 'r') as f:
    content = f.read()
content = re.sub(
    r'https://github.com/Kitware/CMake/releases/download/v3.31.5/cmake-3.31.5.tar.gz.*',
    'https://github.com/Kitware/CMake/releases/download/v3.31.5/cmake-3.31.5.tar.gz    2632b701ff61603ba0cf51f9850e0d5a3ecf459c5307b66df2a51fa16db326ba',
    content
)
with open('recipes/cmake.recipe', 'w') as f:
    f.write(content)
