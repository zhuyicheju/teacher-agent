from werkzeug.security import check_password_hash, generate_password_hash

from cola.domain.factory.Repositoryfactory import users_repository


class AuthService:
    def verify_user(username: str, password: str):
        row = users_repository.get_user_password(username)
        if not row:
            return False
        return check_password_hash(row[0], password)

    def create_user(username: str, password: str):
        if not username or not password:
            return False, "用户名或密码不能为空"
        users_repository.create_user(username, generate_password_hash(password))
        return True, None

auth_service = AuthService()