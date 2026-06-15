# 🏍️💙 Sistema Nacional de Cadastro e Atendimento – Instituto MotoVida Guilherme França

> "Cuidando de quem move o Brasil todos os dias."

Plataforma nacional de cadastro, atendimento e gestão de afiliados (motoboys, motociclistas, entregadores e familiares), com apoio jurídico, psicológico e social, cursos, auxílio MEI e rede de parceiros.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + **FastAPI** + SQLAlchemy |
| Banco de dados | **MySQL 8** (Docker, volume persistente) |
| Frontend | Jinja2 + HTML/CSS responsivo mobile-first (sem dependências externas) |
| Proxy / SSL | **Nginx Proxy Manager** (Let's Encrypt automático) |
| Infra | Docker + docker-compose (com healthcheck) |

FastAPI foi escolhido por ser leve, rápido e simples de containerizar; os templates são servidos pelo próprio backend, então **um único serviço de aplicação** atende área pública, área do afiliado e painel admin.

## Como rodar

Pré-requisito: Docker + Docker Compose.

```bash
# 1. (opcional) configure variáveis de ambiente
cp .env.example .env

# 2. suba tudo
docker compose up --build
```

**Desenvolvimento local:** a aplicação fica em **http://localhost:8000** (acesso direto, sem passar pelo NPM).

**Produção com domínio e HTTPS:** veja a seção [Configuração SSL](#configuração-ssl-produção) abaixo.

No primeiro boot, automaticamente:
- o MySQL é criado com volume persistente (`mysql_data`);
- a aplicação aguarda o banco ficar saudável (healthcheck + retry);
- **todas as tabelas são criadas** (SQLAlchemy `create_all`);
- os **seeds** são aplicados: usuário admin, afiliado de demonstração, 5 cursos, 8 parceiros e 1 evento.

## Usuários de teste

| Perfil | E-mail | Senha |
|---|---|---|
| Administrador | `admin@motovida.org.br` | `admin123` |
| Afiliado demo | `afiliado@teste.com` | `teste123` |

(Os valores podem ser alterados no `.env` antes do primeiro boot.)

## Mapa do sistema

**Área pública** (`/`)
- Página institucional, lista de benefícios, parceiros em destaque
- `/cadastro` — cadastro de afiliado com validação de CPF, e-mail, UF e aceite LGPD obrigatório (data/hora registradas)
- `/parceiros`, `/contato`, `/privacidade`, `/login`

**Área do afiliado** (`/afiliado` — requer login de afiliado)
- Dashboard com resumo dos atendimentos
- `/afiliado/juridico` — acidentes de trânsito, dúvidas trabalhistas/previdenciárias, com status
- `/afiliado/psicologico` — acolhimento emocional, vítima/familiar, preferência de agendamento
- `/afiliado/cursos` — listagem e inscrição em cursos
- `/afiliado/mei` — passo a passo + solicitação de suporte especializado
- `/afiliado/ajuda` — abertura de solicitações (tipo, prioridade, status, histórico completo)

**Painel administrativo** (`/admin` — requer login de admin)
- Dashboard com relatórios: total de afiliados, por estado, por cidade, por profissão, solicitações por tipo/status, cursos com mais inscritos e principais demandas
- `/admin/afiliados` — listagem com filtros por estado, cidade e profissão + detalhe completo + registro de atendimentos
- `/admin/solicitacoes` — gestão de solicitações com alteração de status e histórico
- `/admin/atendimentos` — demandas jurídicas, psicológicas e MEI
- `/admin/cursos` — cadastro/edição de cursos e lista de inscritos
- `/admin/eventos` e `/admin/parceiros` — cadastro e edição

## Configuração SSL (produção)

O `docker-compose.yml` inclui o **Nginx Proxy Manager** que gerencia certificados SSL via Let's Encrypt automaticamente.

### Portas expostas

| Porta | Função |
|---|---|
| `80` | HTTP — redirecionamento para HTTPS e ACME challenge |
| `443` | HTTPS |
| `81` | Painel admin do NPM (pode ser bloqueado no firewall após configurar) |

### Passo a passo

1. Aponte o DNS do seu domínio para o IP do servidor (registro `A`).

2. Suba os containers:
   ```bash
   docker compose up -d
   ```

3. Acesse o painel do NPM: `http://IP_DO_SERVIDOR:81`
   - Login inicial: `admin@example.com` / `changeme`
   - **Troque a senha imediatamente.**

4. Crie um **Proxy Host**:
   - **Domain Names:** `seudominio.com.br`
   - **Forward Hostname:** `motovida-app`
   - **Forward Port:** `8000`
   - Aba **SSL** → "Request a new SSL Certificate" → ative "Force SSL" e "HTTP/2"

5. Pronto — o NPM emite e renova o certificado automaticamente.

> **Firewall:** em produção bloqueie a porta `81` após a configuração inicial e a porta `8000` (o app não deve ser acessível diretamente, apenas via NPM).

## Banco de dados

Tabelas criadas automaticamente: `users`, `affiliates`, `support_requests`, `request_history`, `legal_support`, `psychological_support`, `mei_support`, `courses`, `course_enrollments`, `events`, `partners`, `attendances`, `lgpd_consents`.

Para inspecionar o banco:

```bash
docker exec -it motovida-mysql mysql -u motovida -pmotovida123 motovida
```

## Segurança e LGPD

- Senhas com hash **PBKDF2-SHA256** (260 mil iterações + salt) — nunca em texto puro
- Aceite LGPD obrigatório no cadastro, com **versão da política e data/hora registradas** em `lgpd_consents`
- Política de privacidade pública em `/privacidade`
- Rotas `/admin/*` e `/afiliado/*` protegidas por sessão assinada, com perfis separados (admin × afiliado)
- Validação de CPF (algoritmo oficial dos dígitos verificadores), e-mail e UF
- Sanitização de entradas (remoção de caracteres de controle + limite de tamanho) e escape automático nos templates (Jinja2)

## Estrutura do projeto

```
motovida/
├── docker-compose.yml
├── .env.example
├── README.md
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py            # entrypoint FastAPI (startup: espera DB, cria tabelas, seeds)
        ├── config.py          # variáveis de ambiente
        ├── database.py        # engine, sessão e espera do MySQL
        ├── models.py          # 13 tabelas (SQLAlchemy)
        ├── security.py        # hash de senha PBKDF2
        ├── validators.py      # CPF, e-mail, UF, sanitização
        ├── seeds.py           # admin, afiliado demo, cursos, parceiros, evento
        ├── deps.py            # sessão do usuário, flash e rótulos PT-BR
        ├── routers/
        │   ├── public.py      # home, cadastro, parceiros, contato, privacidade
        │   ├── auth.py        # login / logout
        │   ├── affiliate.py   # área exclusiva do afiliado
        │   └── admin.py       # painel administrativo
        ├── templates/         # Jinja2 (public / affiliate / admin)
        └── static/css/        # estilo responsivo mobile-first
```

## Comandos úteis

```bash
docker compose up --build           # subir tudo (primeira vez)
docker compose up -d                # subir em background
docker compose down                 # parar (mantém os dados)
docker compose down -v              # parar e APAGAR todos os volumes
docker compose logs -f app          # logs da aplicação
docker compose logs -f nginx-proxy-manager  # logs do NPM
```
