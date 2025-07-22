// ================================
// 主应用组件
// Enterprise RAG System Frontend Main Application
// ================================

import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { Amplify } from 'aws-amplify';
import { getCurrentUser } from 'aws-amplify/auth';

// 配置导入
import { amplifyConfig, validateConfig } from '@/config/aws';

// 页面组件导入
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import ChatPage from '@/pages/ChatPage';
import DocumentsPage from '@/pages/DocumentsPage';
import SettingsPage from '@/pages/SettingsPage';

// 布局组件导入
import MainLayout from '@/components/layout/MainLayout';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import NotificationContainer from '@/components/common/NotificationContainer';

// Context导入
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { AppProvider, useApp } from '@/context/AppContext';
import { ThemeProvider as CustomThemeProvider, useTheme } from '@/context/ThemeContext';

// 类型导入
import { User } from '@/types';

// 样式导入
import './App.css';

// 配置Amplify
try {
  Amplify.configure(amplifyConfig);
  console.log('Amplify configured successfully');
} catch (error) {
  console.error('Failed to configure Amplify:', error);
}

// 私有路由组件
const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();
  
  if (isLoading) {
    return <LoadingSpinner />;
  }
  
  return user ? <>{children}</> : <Navigate to="/login" replace />;
};

// 公共路由组件（只有未认证用户可访问）
const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();
  
  if (isLoading) {
    return <LoadingSpinner />;
  }
  
  return !user ? <>{children}</> : <Navigate to="/dashboard" replace />;
};

// 应用路由组件
const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* 公共路由 */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route path="/callback" element={<div>处理登录回调...</div>} />
      <Route path="/logout" element={<div>登出中...</div>} />
      
      {/* 私有路由 */}
      <Route
        path="/"
        element={
          <PrivateRoute>
            <MainLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="chat/:sessionId" element={<ChatPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      
      {/* 404 页面 */}
      <Route path="*" element={<div>页面未找到</div>} />
    </Routes>
  );
};

// 主题组件
const ThemedApp: React.FC = () => {
  const { theme } = useTheme();
  
  const muiTheme = createTheme({
    palette: {
      mode: theme.mode,
      primary: {
        main: theme.primaryColor,
      },
      secondary: {
        main: theme.secondaryColor,
      },
      background: {
        default: theme.backgroundColor,
        paper: theme.mode === 'dark' ? '#1e1e1e' : '#ffffff',
      },
      text: {
        primary: theme.textColor,
      },
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontSize: '2.5rem',
        fontWeight: 600,
      },
      h2: {
        fontSize: '2rem',
        fontWeight: 600,
      },
      h3: {
        fontSize: '1.75rem',
        fontWeight: 500,
      },
      body1: {
        fontSize: '1rem',
        lineHeight: 1.6,
      },
    },
    shape: {
      borderRadius: 12,
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: 8,
            padding: '8px 16px',
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            border: `1px solid ${theme.mode === 'dark' ? '#333' : '#eee'}`,
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 8,
            },
          },
        },
      },
    },
  });

  return (
    <ThemeProvider theme={muiTheme}>
      <CssBaseline />
      <Router>
        <ErrorBoundary>
          <AppRoutes />
          <NotificationContainer />
        </ErrorBoundary>
      </Router>
    </ThemeProvider>
  );
};

// 应用初始化组件
const AppInitializer: React.FC = () => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const { setUser, setLoading } = useAuth();

  useEffect(() => {
    const initializeApp = async () => {
      try {
        setLoading(true);
        
        // 验证配置
        if (!validateConfig()) {
          throw new Error('应用配置验证失败');
        }
        
        // 检查当前用户认证状态
        try {
          const currentUser = await getCurrentUser();
          if (currentUser) {
            const user: User = {
              id: currentUser.userId,
              email: currentUser.signInDetails?.loginId || '',
              name: currentUser.signInDetails?.loginId || '',
              isAuthenticated: true,
            };
            setUser(user);
          }
        } catch (authError) {
          // 用户未认证，这是正常情况
          console.log('User not authenticated');
        }
        
        setIsInitialized(true);
      } catch (error) {
        console.error('App initialization failed:', error);
        setInitError(error instanceof Error ? error.message : '应用初始化失败');
      } finally {
        setLoading(false);
      }
    };

    initializeApp();
  }, [setUser, setLoading]);

  if (!isInitialized) {
    if (initError) {
      return (
        <div style={{ 
          padding: '20px', 
          textAlign: 'center',
          color: 'red',
          fontFamily: 'Inter, sans-serif'
        }}>
          <h2>应用初始化失败</h2>
          <p>{initError}</p>
          <button onClick={() => window.location.reload()}>
            重新加载
          </button>
        </div>
      );
    }
    
    return <LoadingSpinner />;
  }

  return <ThemedApp />;
};

// 主应用组件
const App: React.FC = () => {
  return (
    <CustomThemeProvider>
      <AuthProvider>
        <AppProvider>
          <AppInitializer />
        </AppProvider>
      </AuthProvider>
    </CustomThemeProvider>
  );
};

export default App;