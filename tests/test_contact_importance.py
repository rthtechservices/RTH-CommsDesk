from app.models.entities import Contact
from app.services.contact_service import contact_importance_weight


def test_contact_importance_weight_for_vip_client():
    c = Contact(importance_tier=4, relationship_type="client", is_vip=True, is_noise=False)
    assert contact_importance_weight(c) >= 80


def test_contact_importance_weight_noise_penalty():
    c = Contact(importance_tier=3, relationship_type="friend", is_vip=False, is_noise=True)
    assert contact_importance_weight(c) < 0
