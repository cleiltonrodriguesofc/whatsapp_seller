import pytest
from core.domain.entities import Product
from core.infrastructure.database.repositories import SQLProductRepository, SQLUserRepository
from core.infrastructure.database.models import UserModel

def test_product_repository_save_and_get(db_session):
    repo = SQLProductRepository(db_session)
    
    # Create a test user
    user = UserModel(email="test@repo.com", hashed_password="hashed_password")
    db_session.add(user)
    db_session.commit()
    
    product = Product(
        name="Rep Product",
        description="Rep Description",
        price=50.0,
        affiliate_link="http://link.com",
        user_id=user.id
    )
    
    saved = repo.save(product)
    assert saved.id is not None
    
    fetched = repo.get_by_id(saved.id)
    assert fetched.name == "Rep Product"
    assert fetched.user_id == user.id

def test_user_repository_get_by_email(db_session):
    repo = SQLUserRepository(db_session)
    
    user = UserModel(email="unique@test.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()
    
    fetched = repo.get_by_email("unique@test.com")
    assert fetched is not None
    assert fetched.email == "unique@test.com"

def test_product_repository_list_all(db_session):
    repo = SQLProductRepository(db_session)
    
    # Create a test user
    user = UserModel(email="list@test.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()
    
    p1 = Product(name="P1", description="D1", price=10, affiliate_link="L1", user_id=user.id)
    p2 = Product(name="P2", description="D2", price=20, affiliate_link="L2", user_id=user.id)
    
    repo.save(p1)
    repo.save(p2)
    
    products = repo.list_all(user_id=user.id)
    assert len(products) == 2
