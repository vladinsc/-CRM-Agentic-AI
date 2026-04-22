import numpy as np
from sentence_transformers import SentenceTransformer

class LeadScorer:
    def __init__(self, user_rules: list, ideal_customer_description: str):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.icp_vector = self.model.encode(ideal_customer_description)
        self.user_rules = user_rules


    def score_lead(self, db: Session, persona_id: int, lead_data: dict, lead_description: str):
        """Scores a lead by fetching the persona from the pgvector database."""
        
        # 1. Fetch the Persona and its Rules from the database
        persona = db.query(IcpPersona).filter(IcpPersona.id == persona_id).first()
        rules = db.query(UserIcpRule).filter(UserIcpRule.persona_id == persona_id).all()
        
        if not persona:
            raise ValueError("Persona not found")

        # 2. Get the Rule Score
        rule_score = self.calculate_rule_score(lead_data, rules)

        # 3. Get the Vector Score (The Magic of pgvector)
        # Convert the new lead's text into a vector
        lead_vector = self.model.encode(lead_description)
        
        # pgvector calculates distance (0 is perfect match, 2 is total opposite).
        # We want similarity, so we do: 1 - distance
        similarity_query = db.query(
            (1 - IcpPersona.vector_embedding.cosine_distance(lead_vector)).label("similarity")
        ).filter(IcpPersona.id == persona_id).first()
        
        # Convert the similarity (-1.0 to 1.0) into a 0-100 score
        raw_similarity = similarity_query.similarity if similarity_query.similarity else 0
        vector_score = max(0, raw_similarity) * 100

        # 4. Blend the scores
        total_score = (rule_score * 0.7) + (vector_score * 0.3)

        return {
            "total_score": round(total_score, 1),
            "rule_score": round(rule_score, 1),
            "vector_score": round(vector_score, 1),
            "lead_vector": lead_vector.tolist() # Return as list so the API can return it as JSON
        }

    def evaluate_user_rules(self, lead_data:dict) -> float:
        score = 0
        for rule in self.user_rules:
            field = rule['field']
            target = rule['target']
            points = rule['points']
            operator = rule['operator']
            
            val = lead_data.get(field)
            if val is None:
                continue
                
            if operator == 'equals' and str(val).lower() == str(target).lower():
                score += points
            elif operator == 'greater_than':
                try:
                    if float(val) >= float(target):
                        score += points
                    elif float(val) >= float(target) * 0.8:
                        score += points / 2 # Partial points for being close to the target
                except ValueError:
                    pass
        
        return min(score, 100)
        
    def process_user_feedback(self, lead_vector, user_rating_1_to_10, learning_rate=0.15):
        """
        Shifts the ICP vector based on user feedback.
        A rating of 10 pulls the ICP closer to the lead. A rating of 1 pushes it away.
        """
        # Convert 1-10 rating to a direction scale (-1.0 to 1.0)
        direction = (user_rating_1_to_10 - 5.5) / 4.5
        
        # Apply the shift: V_new = V_icp + (learning_rate * direction * V_lead)
        self.icp_vector = self.icp_vector + (learning_rate * direction * lead_vector)
        
        # Re-normalize the vector to prevent math explosion
        self.icp_vector = self.icp_vector / np.linalg.norm(self.icp_vector)
        print(f"-> AI Vector shifted. Learning rate: {learning_rate}, Direction: {round(direction, 2)}")

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)