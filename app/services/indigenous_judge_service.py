"""Indigenous dish classification service.

This service acts as a judge to determine if a dish is indigenous/traditional
based on vector search results and neutral food identification.
Used as Stage 3 in the 3-stage indigenous dish detection pipeline.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from app.services.base_llm_service import BaseLLMService, LLMServiceError

logger = logging.getLogger(__name__)


class IndigenousJudgeService(BaseLLMService):
    """Service for judging if a dish is indigenous/traditional."""

    # Indigenous countries supported
    INDIGENOUS_COUNTRIES = ["Ghana", "Nigeria", "Jamaica"]

    async def judge_indigenous_classification(
        self,
        encoded_image: str,
        vector_search_results: List[Dict[str, Any]],
        food_identification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Judge whether a dish is indigenous based on multiple evidence sources.
        
        Args:
            encoded_image: Base64 encoded image string
            vector_search_results: Results from vector database search
            food_identification: Results from neutral food identification
            
        Returns:
            Dictionary containing indigenous classification decision
        """
        
        # Prepare context for the judge
        vector_context = self._format_vector_context(vector_search_results)
        food_id_context = self._format_food_identification_context(food_identification)
        
        prompt = f"""You are an expert food culturist specializing in traditional dishes from Ghana, Nigeria, and Jamaica.

Your task is to determine if the food in this image is an indigenous/traditional dish from one of these countries.

EVIDENCE PROVIDED:
{vector_context}

{food_id_context}

CLASSIFICATION CRITERIA:
Indigenous/Traditional dishes must meet these criteria:
1. Originated from Ghana, Nigeria, or Jamaica
2. Uses traditional cooking methods from these cultures
3. Contains indigenous ingredients typical to these regions
4. Has cultural significance in these communities
5. Prepared in traditional presentation style

ANALYSIS INSTRUCTIONS:
1. Compare the image with the vector search matches
2. Analyze the neutral food identification results
3. Look for traditional cooking techniques (e.g., jollof preparation, ackee preparation, palm nut soup methods)
4. Identify indigenous ingredients (e.g., plantain, cassava, ackee, palm oil, scotch bonnet peppers)
5. Assess cultural presentation styles
6. Consider authenticity vs. fusion/modern adaptations

Be CONSERVATIVE in classification:
- Only classify as indigenous if there's strong evidence
- Fusion dishes or modern interpretations should be classified as non-indigenous
- Regular international foods should be classified as non-indigenous
- When in doubt, classify as non-indigenous

Provide your decision in this JSON format:
{{
    "is_indigenous": true/false,
    "confidence": 0.85,
    "country_of_origin": "Ghana/Nigeria/Jamaica" or null,
    "dish_classification": "Traditional/Fusion/International",
    "reasoning": "Detailed explanation of your decision",
    "evidence_analysis": {{
        "vector_match_strength": "Strong/Medium/Weak/None",
        "traditional_ingredients": ["ingredient1", "ingredient2"],
        "cooking_methods": ["method1", "method2"],
        "cultural_markers": ["marker1", "marker2"]
    }},
    "recommendation": "Classify as indigenous/non-indigenous because..."
}}"""

        try:
            logger.info("Performing indigenous classification judgment...")
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
                temperature=0.2,  # Lower temperature for consistent judgment
            )
            
            ai_response = response.choices[0].message.content
            result = json.loads(ai_response)
            
            logger.info(f"Indigenous classification: {result.get('is_indigenous', False)} "
                       f"(confidence: {result.get('confidence', 0):.2f})")
            
            return result

        except Exception as e:
            logger.error(f"Error in indigenous classification: {str(e)}")
            # Return conservative fallback (non-indigenous)
            return {
                "is_indigenous": False,
                "confidence": 0.0,
                "country_of_origin": None,
                "dish_classification": "Unknown",
                "reasoning": f"Classification failed due to error: {str(e)}",
                "evidence_analysis": {
                    "vector_match_strength": "Error",
                    "traditional_ingredients": [],
                    "cooking_methods": [],
                    "cultural_markers": []
                },
                "recommendation": "Classified as non-indigenous due to analysis error"
            }

    def _format_vector_context(self, vector_results: List[Dict[str, Any]]) -> str:
        """Format vector search results for the prompt."""
        if not vector_results:
            return "VECTOR SEARCH RESULTS: No similar dishes found in indigenous database."
        
        context = "VECTOR SEARCH RESULTS:\n"
        for i, dish in enumerate(vector_results[:3], 1):  # Top 3 matches
            context += f"{i}. {dish.get('dish_name', 'Unknown')} "
            context += f"(Country: {dish.get('country', 'Unknown')}, "
            context += f"Similarity: {dish.get('similarity', 0):.3f})\n"
            if dish.get('description'):
                context += f"   Description: {dish.get('description')}\n"
        
        return context

    def _format_food_identification_context(self, food_id: Dict[str, Any]) -> str:
        """Format food identification results for the prompt."""
        context = "NEUTRAL FOOD IDENTIFICATION:\n"
        context += f"- Identified Food: {food_id.get('identified_food', 'Unknown')}\n"
        context += f"- Category: {food_id.get('food_category', 'Unknown')}\n"
        context += f"- Ingredients: {', '.join(food_id.get('visible_ingredients', []))}\n"
        context += f"- Cooking Methods: {', '.join(food_id.get('cooking_methods', []))}\n"
        context += f"- Presentation: {food_id.get('presentation_style', 'Unknown')}\n"
        context += f"- Confidence: {food_id.get('confidence', 0):.2f}\n"
        
        return context


# Create service instance
indigenous_judge_service = IndigenousJudgeService()