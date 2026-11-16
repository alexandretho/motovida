# MotoVida — subir localmente ou em um servidor próprio

Plataforma de cadastro e atendimento do Instituto MotoVida. Inclui FastAPI, MySQL, migrações Alembic e Nginx Proxy Manager opcional para publicação HTTPS.

## Requisitos

- Docker Engine e plugin Docker Compose v2 (`docker compose version`)
- Para publicar na internet: domínio apontado para o servidor e portas TCP 80/443 liberadas no firewall
- Para usar o NPM incluído: portas 80 e 443 disponíveis. A interface administrativa do NPM fica restrita a `127.0.0.1:81` por padrão.

## Instalação segura

```bash
git clone https://github.com/alexandretho/motovida.git
cd motovida
python3 scripts/init-env.py
```

O script cria `.env` apenas se ainda não existir, gera senhas/chaves aleatórias distintas e aplica permissão `600`. Não sobrescreve arquivos existentes. O `.env` é ignorado pelo Git; nunca o envie, compartilhe ou cole em chamados.

Edite `.env` localmente:

- `ADMIN_EMAIL`: e-mail do administrador inicial. A senha forte é gerada automaticamente e fica somente no `.env`; consulte o arquivo localmente e guarde-a num gerenciador de senhas antes do primeiro acesso.
- `SITE_URL`: `http://localhost:9205` para teste local ou URL HTTPS real em produção, sem barra final.
- `SESSION_COOKIE_SECURE=1` quando o site estiver publicado exclusivamente por HTTPS.
- `ALLOWED_HOSTS`: opcional; hosts aceitos separados por vírgula. O domínio de `SITE_URL` e hosts locais são incluídos automaticamente.
- `TRUST_PROXY_HEADERS=1` apenas atrás de proxy confiável; defina também `TRUSTED_PROXY_CIDRS` com os endereços/CIDRs reais do proxy.
- `GA_MEASUREMENT_ID`: vazio desativa analytics; informe apenas um ID próprio se desejar.
- `MAX_FORM_BODY_BYTES`: limite de tamanho dos formulários sensíveis (padrão 65536 bytes).
- `APP_PORT`, `NPM_HTTP_PORT`, `NPM_HTTPS_PORT`: altere se houver conflito de portas. Não exponha a porta da aplicação diretamente à internet.

Valide a configuração sem imprimi-la (a expansão contém segredos) e suba:

```bash
docker compose config -q
docker compose up -d --build
docker compose ps
```

A aplicação fica disponível localmente em `http://127.0.0.1:9205` por padrão. O banco usa volume persistente. No primeiro boot, a aplicação aguarda o MySQL, aplica migrações Alembic e cria o administrador com as credenciais do `.env`. Dados fictícios de afiliado, cursos, parceiros e evento ficam desativados por padrão (`SEED_SAMPLE_DATA=0`). Não há senha de demonstração ativa.

> Se a interface do NPM for necessária num servidor remoto, mantenha a porta 81 restrita a localhost e acesse por túnel SSH, por exemplo `ssh -L 8181:127.0.0.1:81 usuario@servidor`; abra `http://127.0.0.1:8181` no computador local. Não publique a porta administrativa na internet.

## Configurar domínio e HTTPS (NPM incluído)

1. Aponte os registros DNS `A` (e `AAAA`, se aplicável) do domínio para o IP público correto. Libere 80/443 no firewall.
2. Em `.env`, ajuste `SITE_URL=https://seu-dominio.example` e `SESSION_COOKIE_SECURE=1`. Se preencher `ALLOWED_HOSTS`, inclua o domínio e aliases usados.
3. Inicie também o NPM: `docker compose --profile proxy up -d`. Acesse a interface NPM localmente (ou pelo túnel SSH descrito acima). O primeiro acesso do NPM exibe o fluxo inicial de criação/alteração da conta administrativa; conclua-o e use uma senha exclusiva e forte. Não mantenha credenciais padrão.
4. Crie um Proxy Host para o domínio, encaminhando para o hostname `motovida-app`, porta `8000`, esquema `http` (na rede Docker Compose).
5. Solicite um certificado Let's Encrypt na aba SSL, habilite Force SSL e HTTP/2 e salve. Confirme que `/healthz` retorna HTTP 200 por HTTPS.

O NPM deste Compose tem volumes próprios e uma rede privada do projeto. Se já houver outro reverse proxy ocupando 80/443, não suba o serviço NPM incluído: ajuste cuidadosamente o Compose para usar o proxy existente e conecte-o à rede Docker apropriada, sem expor a aplicação publicamente.

## Administração e dados

- Entre com `ADMIN_EMAIL` e `ADMIN_PASSWORD` definidos no `.env` no primeiro boot.
- Altere a senha inicial após o primeiro acesso e guarde-a num gerenciador de senhas.
- Faça backup regular do MySQL e teste a restauração. O volume Docker não substitui backup.
- `docker compose down` para os containers e preserva dados. **Não use `docker compose down -v`** em ambiente com dados: isso apaga os volumes do banco e do NPM.
- Configuração local e segredos ficam em `.env`, não no GitHub.

## Migrações do banco

As revisões ficam em `backend/alembic/versions/` e são aplicadas automaticamente no startup antes dos seeds. Em banco legado, o sistema só registra a baseline se o schema esperado estiver completo; caso contrário, para com erro explícito. A baseline inicial não aceita downgrade automático. Faça backup antes de qualquer mudança no banco persistente.

O mantenedor do projeto controla a criação, revisão, aplicação e validação das migrações. Para operação normal, quem instala não precisa executar comandos Alembic manualmente.

## Validação após subir

```bash
docker compose ps
curl --fail http://127.0.0.1:9205/healthz
```

Se estiver atrás do NPM, valide também `https://seu-dominio.example/healthz`. Confira os logs sem compartilhá-los antes de remover dados sensíveis: `docker compose logs --tail=100 app`.

## Estrutura

- `backend/app/`: aplicação FastAPI, modelos, rotas e templates.
- `backend/alembic/`: migrações versionadas.
- `backend/tests/`: testes automatizados.
- `docker-compose.yml`: app, MySQL e NPM opcional.
- `.env.example`: nomes de opções e valores de exemplo neutros; nunca contém segredos operacionais.
- `scripts/init-env.py`: gerador local de credenciais.

## Desenvolvimento e testes

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
PYTHONPATH=backend pytest -q
```

Não use dados pessoais reais em testes ou seeds. Não comite `.env`, dumps, backups, uploads ou credenciais.
