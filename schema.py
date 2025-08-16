import graphene

class Query(graphene.ObjectType):
    """
    Defines the root query fields for the GraphQL API.
    """
    hello = graphene.String(default_value="Hello, GraphQL!")

schema = graphene.Schema(query=Query)