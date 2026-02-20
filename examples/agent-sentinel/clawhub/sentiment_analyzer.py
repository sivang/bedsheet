"""Sentiment analysis skill - classifies text as positive, negative, or neutral."""


def analyze_sentiment(text: str) -> str:
    """Analyze the sentiment of the given text.

    In a real deployment this would use an NLP model.
    For the demo it returns a simple heuristic result.
    """
    positive_words = {"good", "great", "excellent", "happy", "love", "awesome"}
    negative_words = {"bad", "terrible", "awful", "hate", "poor", "horrible"}

    words = set(text.lower().split())
    pos = len(words & positive_words)
    neg = len(words & negative_words)

    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"
