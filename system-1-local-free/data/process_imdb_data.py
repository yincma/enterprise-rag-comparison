#!/usr/bin/env python3
"""
Process IMDB datasets for RAG system
"""
import pandas as pd
import json
import os
from pathlib import Path

def load_and_process_basics():
    """Load and process title basics data"""
    print("Processing title basics...")
    
    # Load data with proper dtypes
    df = pd.read_csv('imdb_datasets/title.basics.tsv', sep='\t', na_values=['\\N'], low_memory=False)
    
    # Convert numeric columns
    df['startYear'] = pd.to_numeric(df['startYear'], errors='coerce')
    df['runtimeMinutes'] = pd.to_numeric(df['runtimeMinutes'], errors='coerce')
    
    # Filter for movies only (exclude shorts, TV episodes, etc.)
    movies = df[df['titleType'].isin(['movie'])]
    
    # Filter for movies with proper year and runtime
    movies = movies[
        (movies['startYear'].notna()) & 
        (movies['startYear'] >= 1900) & 
        (movies['runtimeMinutes'].notna()) &
        (movies['runtimeMinutes'] >= 60)  # At least 60 minutes
    ]
    
    print(f"Found {len(movies)} movies")
    return movies

def load_ratings():
    """Load ratings data"""
    print("Loading ratings...")
    ratings = pd.read_csv('imdb_datasets/title.ratings.tsv', sep='\t')
    print(f"Found {len(ratings)} ratings")
    return ratings

def load_names():
    """Load person names data"""
    print("Loading person names...")
    names = pd.read_csv('imdb_datasets/name.basics.tsv', sep='\t', na_values=['\\N'])
    print(f"Found {len(names)} people")
    return names

def merge_movie_data(movies, ratings):
    """Merge movies with ratings"""
    print("Merging movie data with ratings...")
    
    # Merge movies with ratings
    movies_with_ratings = movies.merge(ratings, on='tconst', how='inner')
    
    # Filter for popular movies (at least 1000 votes)
    popular_movies = movies_with_ratings[movies_with_ratings['numVotes'] >= 1000]
    
    print(f"Found {len(popular_movies)} popular movies")
    return popular_movies

def create_movie_documents(movies_df):
    """Create document-like entries for RAG system"""
    documents = []
    
    for _, movie in movies_df.iterrows():
        # Create rich text description
        doc = {
            'id': movie['tconst'],
            'title': movie['primaryTitle'],
            'original_title': movie['originalTitle'],
            'year': int(movie['startYear']) if pd.notna(movie['startYear']) else None,
            'runtime': int(movie['runtimeMinutes']) if pd.notna(movie['runtimeMinutes']) else None,
            'genres': movie['genres'].split(',') if pd.notna(movie['genres']) else [],
            'rating': float(movie['averageRating']) if pd.notna(movie['averageRating']) else None,
            'votes': int(movie['numVotes']) if pd.notna(movie['numVotes']) else None
        }
        
        # Create searchable text content
        text_parts = [
            f"Title: {movie['primaryTitle']}",
        ]
        
        if pd.notna(movie['originalTitle']) and movie['originalTitle'] != movie['primaryTitle']:
            text_parts.append(f"Original Title: {movie['originalTitle']}")
            
        if pd.notna(movie['startYear']):
            text_parts.append(f"Year: {int(movie['startYear'])}")
            
        if pd.notna(movie['runtimeMinutes']):
            text_parts.append(f"Runtime: {int(movie['runtimeMinutes'])} minutes")
            
        if pd.notna(movie['genres']):
            text_parts.append(f"Genres: {movie['genres']}")
            
        if pd.notna(movie['averageRating']):
            text_parts.append(f"Rating: {movie['averageRating']}/10 ({movie['numVotes']} votes)")
        
        doc['content'] = ' | '.join(text_parts)
        documents.append(doc)
    
    return documents

def load_sample_reviews():
    """Load sample reviews"""
    with open('imdb_datasets/sample_reviews.json', 'r') as f:
        reviews = json.load(f)
    
    # Convert to document format
    review_docs = []
    for i, review in enumerate(reviews):
        doc = {
            'id': f'review_{i}',
            'content': f"Movie Review (Rating: {review['rating']}/10, Sentiment: {review['label']}): {review['text']}",
            'sentiment': review['label'],
            'rating': review['rating'],
            'text': review['text']
        }
        review_docs.append(doc)
    
    return review_docs

def save_processed_data():
    """Main processing function"""
    os.makedirs('processed', exist_ok=True)
    
    # Process movie data
    movies = load_and_process_basics()
    ratings = load_ratings()
    movies_with_ratings = merge_movie_data(movies, ratings)
    
    # Take top 1000 movies for demo
    top_movies = movies_with_ratings.nlargest(1000, 'numVotes')
    movie_documents = create_movie_documents(top_movies)
    
    # Save movie documents
    with open('processed/movies.json', 'w') as f:
        json.dump(movie_documents, f, indent=2)
    
    print(f"Saved {len(movie_documents)} movie documents")
    
    # Process reviews
    review_documents = load_sample_reviews()
    
    with open('processed/reviews.json', 'w') as f:
        json.dump(review_documents, f, indent=2)
    
    print(f"Saved {len(review_documents)} review documents")
    
    # Create combined dataset
    all_documents = movie_documents + review_documents
    
    with open('processed/combined_data.json', 'w') as f:
        json.dump(all_documents, f, indent=2)
    
    print(f"Saved {len(all_documents)} total documents to combined_data.json")
    
    # Create sample queries
    sample_queries = [
        "What are some good comedy movies from the 1990s?",
        "Find highly rated action movies",
        "Show me movies with good reviews",
        "What are the best movies of all time?",
        "Find movies similar to Titanic",
        "Show me recent sci-fi movies",
        "What are some good romantic comedies?",
        "Find movies with high ratings but few votes"
    ]
    
    with open('processed/sample_queries.json', 'w') as f:
        json.dump(sample_queries, f, indent=2)
    
    print("Processing complete!")
    print("\nFiles created:")
    print("- processed/movies.json: Movie data")
    print("- processed/reviews.json: Review data") 
    print("- processed/combined_data.json: All data combined")
    print("- processed/sample_queries.json: Sample queries to test")

if __name__ == "__main__":
    save_processed_data()