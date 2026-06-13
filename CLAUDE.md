# Instituto MotoVida Guilherme França — Contexto do Projeto

Sistema Nacional de Cadastro e Atendimento para motoboys, motociclistas, entregadores e familiares. Apoio jurídico, psicológico e social, cursos, auxílio MEI e rede de parceiros.

## Stack e arquitetura

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy, templates Jinja2 servidos pelo próprio backend (sem SPA)
- **Banco:** MySQL 8 em Docker, volume persistente `mysql_data`
- **Frontend:** HTML/CSS responsivo mobile-first em `backend/app/static/css/style.css`, sem dependências externas (sem CDN)
- **Execução:** `docker compose up --build` → http://localhost:8000

## Como rodar e testar

- Admin: `admin@motovida.org.br` / `admin123`
- Afiliado demo: `afiliado@teste.com` / `teste123`
- Tabelas criadas no startup (`Base.metadata.create_all`); seeds em `backend/app/seeds.py` rodam só se o banco estiver vazio
- Inspecionar banco: `docker exec -it motovida-mysql mysql -u motovida -pmotovida123 motovida`

## Estrutura

- `backend/app/main.py` — entrypoint; startup espera o MySQL (retry), cria tabelas e aplica seeds
- `backend/app/models.py` — 13 tabelas: users, affiliates, support_requests, request_history, legal_support, psychological_support, mei_support, courses, course_enrollments, events, partners, attendances, lgpd_consents
- `backend/app/routers/` — `public.py` (home, cadastro, parceiros), `auth.py` (login/logout), `affiliate.py` (área `/afiliado`), `admin.py` (painel `/admin`)
- `backend/app/deps.py` — sessão do usuário, mensagens flash e dicionário `L` de rótulos PT-BR usado em todos os templates
- `backend/app/security.py` — hash PBKDF2-SHA256 (260k iterações); nunca armazenar senha em texto puro
- `backend/app/validators.py` — CPF (dígitos verificadores), e-mail, UF, sanitização

## Convenções do projeto

- Enums de domínio definidos em `models.py` (PROFESSIONS, MEI_STATUSES, REQUEST_TYPES, PRIORITIES, STATUSES) — validar entrada sempre contra eles
- Status: aberta, em_analise, em_atendimento, concluida, cancelada · Prioridades: baixa, media, alta, urgente
- Rotas protegidas usam `require_affiliate`/`require_admin` + `guard()`; POST sempre redireciona com 303 + mensagem flash
- Toda entrada de formulário passa por `sanitize()`; rótulos exibidos via `L` (nunca mostrar o valor cru do enum)
- Aceite LGPD é obrigatório no cadastro e registrado com versão e data/hora em `lgpd_consents`

## Pendências conhecidas (backlog)

1. Eventos só existem no admin — falta página pública/afiliado para visualizá-los, e falta edição/desativação de eventos
2. Agendamento psicológico é só texto livre — admin não confirma data/hora
3. Atendimentos especializados (jurídico/psico/MEI) não registram histórico de mudança de status (só o Canal de Ajuda registra, em `request_history`)
4. Afiliado não edita o próprio perfil nem recupera senha
5. Página de contato sem formulário funcional
6. Sem gestão de usuários administradores (criar novos admins, trocar senha)
7. Sem proteção CSRF nos formulários (cookie SameSite=lax apenas)
8. Sem migrações (Alembic) — mudanças de schema exigem cuidado com o volume existente
9. Sem paginação nas listagens do admin
10. App nunca foi executado de ponta a ponta com Docker — validar o primeiro `docker compose up --build` e corrigir eventuais erros de runtime