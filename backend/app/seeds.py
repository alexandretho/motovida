from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from . import models
from .config import ADMIN_EMAIL, ADMIN_PASSWORD, POLICY_VERSION
from .security import hash_password


def run_seeds(db: Session):
    if db.query(models.User).count() > 0:
        return

    admin = models.User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), role="admin")
    db.add(admin)

    courses = [
        ("Educação e conscientização no trânsito", "Fundamentos de comportamento seguro, legislação e convivência no trânsito urbano.", "Trânsito", 8),
        ("Direção defensiva para motociclistas", "Técnicas de pilotagem preventiva, frenagem, posicionamento e antecipação de riscos.", "Trânsito", 12),
        ("Primeiros socorros", "Como agir nos primeiros minutos após um acidente até a chegada do socorro.", "Saúde", 6),
        ("Segurança para motociclistas", "Equipamentos de proteção, manutenção preventiva e checklist diário da moto.", "Segurança", 8),
        ("Desenvolvimento profissional do entregador", "Finanças pessoais, atendimento, organização de rotas e crescimento na profissão.", "Carreira", 10),
    ]
    for title, desc, cat, hours in courses:
        db.add(models.Course(title=title, description=desc, category=cat, workload_hours=hours))

    partners = [
        ("Oficina Duas Rodas", "Oficinas mecânicas", "15% em revisões e mão de obra", "São Paulo", "SP", "(11) 99999-0001"),
        ("Moto Peças Brasil", "Lojas de peças e acessórios", "10% em peças originais", "Belo Horizonte", "MG", "(31) 99999-0002"),
        ("Clínica Vida & Saúde", "Clínicas médicas", "Consultas a preço social", "Rio de Janeiro", "RJ", "(21) 99999-0003"),
        ("Farmácia Popular do Centro", "Farmácias", "12% em medicamentos", "Curitiba", "PR", "(41) 99999-0004"),
        ("Escola Profissional Avante", "Cursos profissionalizantes", "20% em cursos técnicos", "Recife", "PE", "(81) 99999-0005"),
        ("Seguro Confiança Moto", "Seguros", "Plano especial para entregadores", "São Paulo", "SP", "(11) 99999-0006"),
        ("Rede Posto Econômico", "Combustíveis", "R$ 0,10 de desconto por litro", "Goiânia", "GO", "(62) 99999-0007"),
        ("Academia Corpo em Movimento", "Academias", "Mensalidade com 25% off", "Fortaleza", "CE", "(85) 99999-0008"),
    ]
    for name, cat, disc, city, state, contact in partners:
        db.add(models.Partner(name=name, category=cat, discount=disc, city=city, state=state, contact=contact))

    db.add(models.Event(
        title="Palestra: Segurança no trânsito salva vidas",
        description="Encontro presencial com especialistas em trânsito e convidados do Instituto.",
        event_date=datetime.utcnow() + timedelta(days=30),
        location="Auditório do Instituto MotoVida",
    ))

    # Afiliado de demonstração (CPF válido gerado para testes)
    demo_user = models.User(email="afiliado@teste.com", password_hash=hash_password("teste123"), role="affiliate")
    db.add(demo_user)
    db.flush()
    demo = models.Affiliate(
        user_id=demo_user.id, full_name="João da Silva Demo", cpf="52998224725",
        phone="(11) 98888-7777", whatsapp="(11) 98888-7777", email="afiliado@teste.com",
        city="São Paulo", state="SP", profession="motoboy", mei_status="quero_abrir_mei",
        support_needs="Quero ajuda para abrir o MEI e participar de cursos.",
    )
    db.add(demo)
    db.flush()
    db.add(models.LgpdConsent(affiliate_id=demo.id, accepted=True, policy_version=POLICY_VERSION))
    db.add(models.SupportRequest(
        affiliate_id=demo.id, type="mei", priority="media",
        description="Preciso de orientação para abrir meu MEI como entregador.",
    ))

    db.commit()
    print("[motovida] Seeds aplicados: admin, afiliado demo, cursos, parceiros e evento.")
