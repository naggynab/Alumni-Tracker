# The account/user model is Django's built-in User plus allauth's email
# handling. The link between a signed-in account and an alumnus record lives on
# directory.Alumnus.user_account (a OneToOneField), so no extra model is needed
# here. This module is intentionally minimal.
