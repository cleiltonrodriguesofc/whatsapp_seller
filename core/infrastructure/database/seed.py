import os
import sys

# Ensure core is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from core.infrastructure.database.session import SessionLocal
from core.infrastructure.database.repositories import SQLProductRepository
from core.domain.entities import Product

def seed():
    db = SessionLocal()
    product_repo = SQLProductRepository(db)
    
    # ASUS Vivobook precise product data
    asus = Product(
        name="Notebook ASUS Vivobook Go 15 Intel Core i3 N305 8GB RAM SSD 256GB Full HD Windows 11",
        description=(
            "O notebook ASUS Vivobook Go 15 E1504GA-NJ434W foi projetado para torná-lo produtivo e mantê-lo entretido. "
            "Com processador Intel Core i3 N305 de 12ª geração, 8GB de RAM e SSD de 256GB. "
            "Tela LED NanoEdge de 15,6\" Full HD com dobradiça de 180º e tampa de privacidade na webcam. "
            "Leve e fino com apenas 1,63kg e durabilidade de nível militar MIL-STD-810H."
        ),
        price=3068.07,
        affiliate_link="https://divulgador.magalu.com/-GhxL_3w",
        image_url="https://a-static.mlcdn.com.br/800x560/notebook-asus-vivobook-go-15-intel-core-i3-n305-8gb-256gb-ssd-156-full-hd-windows-11/magasul/237194600/6e7a5c5c0c6e8e8e8e8e8e8e8e8e8e8e.jpg",
        category="Informática"
    )
    
    product_repo.save(asus)
    print(f"Seeded product: {asus.name}")
    db.close()

if __name__ == "__main__":
    seed()
