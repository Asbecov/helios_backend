from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from helios_backend.db.models.vpn.user import User
from helios_backend.services.auth.jwt import JwtService
from helios_backend.services.users.service import UserService
from helios_backend.web.dependencies.services import get_jwt_service, get_user_service

bearer_auth = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_auth)],
    jwt_service: JwtService = Depends(get_jwt_service),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Resolve and validate the authenticated user from a bearer token."""
    try:
        user_id = jwt_service.decode_access_token(credentials.credentials)
        user = await user_service.get_user_by_id(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
