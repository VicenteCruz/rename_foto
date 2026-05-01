# 📸 Organizador de Fotos Inteligente

Um script Python poderoso e intuitivo para organizar as tuas bibliotecas de fotos e vídeos de forma automática, baseando-se na data em que foram tirados.

## ✨ Funcionalidades

- **Organização Cronológica:** Cria automaticamente pastas por Ano e Mês (ex: `2023/2023_10`).
- **Extração Inteligente de Datas:** Lê metadados EXIF das imagens ou tenta detetar a data no nome do ficheiro.
- **Correção de Tempo:** Permite ajustar o horário das fotos (offset) caso o relógio da câmara estivesse errado.
- **Nomes Personalizados:** Opção para adicionar um prefixo (ex: "Viagem_Lisboa") e escolher se pretendes manter o nome original do ficheiro.
- **Gestão de Duplicados:** Verifica o "hash" (impressão digital) do ficheiro para evitar copiar fotos repetidas, poupando espaço.
- **Suporte a ZIP:** Processa fotos diretamente de ficheiros compactados.
- **Interface Gráfica (GUI):** Fácil de usar, sem necessidade de tocar no código.

## 🚀 Como Usar

### Pré-requisitos
- Python 3.x instalado.
- Bibliotecas necessárias:
  ```bash
  pip install pillow
  ```

### Execução
1. Faz o download do ficheiro `organize_photos.py`.
2. Executa no terminal:
   ```bash
   python organize_photos.py
   ```
3. Seleciona a pasta de **Origem** (onde estão as fotos misturadas) e a de **Destino**.
4. Configura o nome e a correção de tempo se necessário.
5. Clica em **INICIAR ORGANIZAÇÃO**.

## 🛠️ Tecnologias
- **Python** (Core)
- **Tkinter** (Interface Gráfica)
- **Pillow** (Processamento de Imagem/EXIF)

---
*Desenvolvido para tornar a gestão de memórias mais simples e organizada.*
