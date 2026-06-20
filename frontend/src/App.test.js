import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import App from './App';

jest.mock(
  'react-router-dom',
  () => ({
    BrowserRouter: ({ children }) => <div>{children}</div>,
    Routes: ({ children }) => <div>{children}</div>,
    Route: ({ element }) => element,
    Navigate: ({ to }) => <div>Redirect to {to}</div>,
    Link: ({ children, to, ...props }) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
    useNavigate: () => jest.fn(),
  }),
  { virtual: true }
);

jest.mock('./store/authSlice', () => ({
  __esModule: true,
  default: (state = { isLoggedIn: false, isLoading: false, user: null }, action) => state,
  loadUser: () => ({ type: 'auth/loadUser' }),
  logout: () => ({ type: 'auth/logout' }),
  reset: () => ({ type: 'auth/reset' }),
}));

jest.mock('./components/Login', () => () => <div>Login page</div>);
jest.mock('./components/Register', () => () => <div>Register page</div>);
jest.mock('./components/Dashboard', () => () => <div>Dashboard page</div>);
jest.mock('./components/HomePage', () => () => <div>Home page</div>);

test('renders the application shell', () => {
  const store = configureStore({
    reducer: {
      auth: (state = { isLoggedIn: false, isLoading: false, user: null }) => state,
    },
  });

  render(
    <Provider store={store}>
      <App />
    </Provider>
  );

  expect(screen.getByText(/home page/i)).toBeInTheDocument();
});