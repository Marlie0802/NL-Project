from database import Base, engine
import models


print("ChallengeLab database initialiseren...")

Base.metadata.create_all(bind=engine)

print("Database gereed.")
