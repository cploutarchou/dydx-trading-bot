export interface LoginFormErrors {
  username: string;
  password: string;
}

export const getLoginFormErrors = ({
  username,
  password,
}: {
  username: string;
  password: string;
}): LoginFormErrors => ({
  username: username.trim().length === 0 ? 'Enter your username or email.' : '',
  password: password.length === 0 ? 'Enter your password.' : '',
});

export const canSubmitLoginForm = ({
  username,
  password,
  loading,
}: {
  username: string;
  password: string;
  loading: boolean;
}): boolean => username.trim().length > 0 && password.length > 0 && !loading;
