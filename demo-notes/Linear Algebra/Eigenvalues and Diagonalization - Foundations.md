---
tags:
  - linear-algebra
status: growing
---
# Eigenvalues and Diagonalization - Foundations
This note introduces eigenvalues, eigenvectors, and diagonalization. It will be extended with more examples of related methods.

Related practice: [[Past Exams#Exercise 2 (8 pts)|Eigenvalues and diagonalizability]], [[Past Exams#Exercise 2 (9 pts)|Orthogonal diagonalization]]

## Eigenvalues and eigenvectors
An **eigenvector** of a square matrix $A$ is a nonzero vector $v$ such that applying $A$ only scales it. The **eigenvalue** $\lambda$ is the scale factor.

*Example*: For $A=\begin{bmatrix}2&0\\0&3\end{bmatrix}$, the vector $(1,0)$ is an eigenvector with eigenvalue $2$.

The defining equation is
$$
Av=\lambda v.
$$

To find eigenvalues, rewrite this as $(A-\lambda I)v=0$. A nonzero solution exists exactly when $A-\lambda I$ is singular, so solve the characteristic equation
$$
\det(A-\lambda I)=0.
$$

*Example*: For $B=\begin{bmatrix}4&1\\2&3\end{bmatrix}$, the characteristic polynomial is $(\lambda-5)(\lambda-2)$, so its eigenvalues are $5$ and $2$.

For each eigenvalue, solve $(A-\lambda I)v=0$ to find its eigenspace.

## Diagonalization
A **diagonalization** expresses $A$ as $A=PDP^{-1}$, where columns of $P$ are linearly independent eigenvectors and diagonal entries of $D$ are the matching eigenvalues.

*Example*: If $P$ has eigenvectors $v_1,v_2$ as columns, then $D$ must list their eigenvalues in the same order.

A matrix is diagonalizable when it has enough independent eigenvectors to form a basis. Distinct eigenvalues give linearly independent eigenvectors.

## Orthogonal diagonalization
A real matrix is orthogonally diagonalizable when $A=QDQ^T$, where $Q^TQ=I$ and the columns of $Q$ are orthonormal eigenvectors. Real symmetric matrices admit an orthogonal diagonalization.

*Example*: For $C=\begin{bmatrix}1&2&0\\2&1&0\\0&0&3\end{bmatrix}$, an orthonormal eigenbasis yields diagonal entries $3,3,-1$ in the corresponding order.

> [!important] Match eigenvectors and eigenvalues
> In a diagonalization, each diagonal entry of $D$ must match the eigenvalue of the corresponding column of $P$ or $Q$.
FILE>>
