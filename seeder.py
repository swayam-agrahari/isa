import os
import random
from datetime import datetime, timedelta
from faker import Faker

# --- Important: Adjust this import to match your Flask app structure ---
# This assumes your Flask 'app' and 'db' instances are created in a file named 'isa.py'
# or are available from the 'isa' package.
from isa import app, db
from isa.models import User, Campaign, Contribution,Suggestion,Image

# --- Configuration ---
NUM_USERS = 50
NUM_CAMPAIGNS = 10
NUM_CONTRIBUTIONS = 5000
START_DATE = datetime(2019, 1, 1)
END_DATE = datetime(2025, 9, 25) # Today's date for realistic data range

# Initialize Faker for data generation
fake = Faker()

def get_random_date(start, end):
    """Generate a random datetime between two datetime objects."""
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)

def seed_data():
    """
    Main function to clear existing data and populate the database with new fake data.
    """
    with app.app_context():
        print("Starting database seeding...")

        # --- 1. Clean up existing data ---
        print("Deleting existing data...")
        Contribution.query.delete()

        # Delete images before campaigns (depends on Campaign)
        Image.query.delete()

        # Delete suggestions (depends on Campaign and User)
        Suggestion.query.delete()

        # Now delete campaigns and users
        Campaign.query.delete()
        User.query.delete()
        db.session.commit()
        print("Existing data deleted.")

        # --- 2. Create Users ---
        users = []
        for _ in range(NUM_USERS):
            user = User(
                username=fake.unique.user_name(),
                caption_languages=random.choice(['en', 'es', 'fr', 'de']),
                depicts_language=random.choice(['en', 'es', 'fr', 'de', '']),
                contrib=0 # We will update this later
            )
            users.append(user)
        db.session.bulk_save_objects(users)
        db.session.commit()
        # Retrieve users with their generated IDs
        all_users = User.query.all()
        print(f"{len(all_users)} users created.")

        # --- 3. Create Campaigns ---
        campaigns = []
        for _ in range(NUM_CAMPAIGNS):
            manager = random.choice(all_users)
            campaign = Campaign(
                campaign_name=fake.sentence(nb_words=4),
                short_description=fake.paragraph(nb_sentences=2),
                long_description=fake.paragraph(nb_sentences=5),
                categories=fake.word(),
                manager_id=manager.id,
                campaign_manager=manager.username,
                start_date=get_random_date(START_DATE, END_DATE - timedelta(days=30)),
                end_date=get_random_date(END_DATE, END_DATE + timedelta(days=90)),
                status=random.choice([True, False]),
                campaign_type=random.choice([True, False]),
                depicts_metadata=random.choice([True, False]),
                captions_metadata=random.choice([True, False])
            )
            campaigns.append(campaign)
        db.session.bulk_save_objects(campaigns)
        db.session.commit()
        all_campaigns = Campaign.query.all()
        print(f"{len(all_campaigns)} campaigns created.")

        # --- 4. Create Contributions ---
        contributions = []
        
        # Create a weighted user list to simulate power users
        # The first 20% of users will be 10x more likely to contribute
        power_user_count = int(len(all_users) * 0.2)
        power_users = all_users[:power_user_count]
        other_users = all_users[power_user_count:]
        weighted_user_list = (power_users * 10) + other_users
        

        for i in range(NUM_CONTRIBUTIONS):
            user = random.choice(weighted_user_list)
            campaign = random.choice(all_campaigns)
            contribution = Contribution(
                user_id=user.id,
                username=user.username,
                campaign_id=campaign.id,
                file=f"File_{i}_{fake.word()}.jpg",
                edit_type=random.choice(['caption', 'depict']),
                edit_action=random.choice(['add', 'remove']),
                country = fake.country()[:50],
                date=get_random_date(START_DATE, END_DATE)
            )
            contributions.append(contribution)

        print("Adding contributions to the session (this might take a moment)...")
        db.session.bulk_save_objects(contributions)
        db.session.commit()
        print(f"{len(contributions)} contributions created.")

        print("\nDatabase seeding complete!")


if __name__ == '__main__':
    seed_data()
