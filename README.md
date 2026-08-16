# LIOR Company — V9

## Abrir no Windows

1. Extraia o ZIP inteiro.
2. Dê dois cliques em **ABRIR_LOJA.bat**.
3. O navegador abrirá sozinho em `http://127.0.0.1:3000`.
4. Mantenha a janela preta aberta enquanto usar a loja.

O iniciador procura o Python no computador. Quando ele não está instalado, tenta instalar automaticamente pelo `winget`.

## O que foi corrigido

- Categorias com o mesmo tamanho e alinhamento.
- Três cartões na primeira linha e dois centralizados na segunda.
- O filtro mostra somente a categoria escolhida.
- **Todas** volta a mostrar as cinco categorias.
- Conta, cadastro e login funcionam pelo servidor Python e banco SQLite.
- Senhas usam PBKDF2; sessões usam cookie HttpOnly e proteção CSRF.

## Google e pagamentos reais

Para ativar Google e Mercado Pago, copie `server_python/.env.example` para `server_python/.env` e preencha as credenciais. O iniciador já cria esse arquivo automaticamente na primeira abertura.

Não abra o `index.html` diretamente: conta e pagamentos dependem do servidor.

V10: imagens das categorias recortadas novamente sem cortes, rebarbas ou bordas duplicadas.
