---
tags:
  - linear-algebra
---
# Quick Links
- **Past Exams**:
	- [[#18 June 2026 Exam]]
		1. **(6 pts)** **Determinants:** *Invertibility* (compute $\det(A)$ and decide whether $A$ is invertible)
		2. **(8 pts)** **Eigenvalues:** *Diagonalizability* (find the eigenvalues and eigenvectors of $B$, then justify whether it is diagonalizable)
		3. **(8 pts)** **Orthogonality:** *Gram-Schmidt and projection* (find an orthonormal basis of $W$ and project $v$ onto $W$)
		4. **(8 pts)** **Linear systems:** *Solution classification* (classify the system by $k$)
	- [[#10 February 2026 Exam]]
		1. **(5 pts)** **Rank and nullity:** *Rank-nullity theorem* (state the theorem and apply it to $f$; the matrix $M$ is not included in the provided material)
		2. **(9 pts)** **Eigenvalues:** *Orthogonal diagonalization* (diagonalize $C$ with an orthogonal matrix)
		3. **(8 pts)** **Linear maps:** *Kernel and image* (find the kernel and image of $g$)
		4. **(8 pts)** **Eigenvalues:** *Linear independence* (prove that eigenvectors for distinct eigenvalues are linearly independent)
# Memorize
- [[#Exercise 1 (6 pts)|Determinant and invertibility]]
- [[#Exercise 2 (8 pts)|Eigenvalues and diagonalizability]]
- [[#Exercise 4 (8 pts)|Classifying a parameterized system]]
- [[#Exercise 1 (5 pts)|Rank-nullity theorem]]
- [[#Exercise 2 (9 pts)|Orthogonal diagonalization]]
- [[#Exercise 4 (8 pts)|Independence of eigenvectors]]
# Solve again
- [[#Exercise 3 (8 pts)|Gram-Schmidt and projection]]
- [[#Exercise 3 (8 pts)|Kernel and image]]
# Past Exams
## 18 June 2026 Exam
### Exercise 1 (6 pts)
**Original question:** Compute the determinant of $A=\begin{bmatrix}2&1&0\\1&3&1\\0&1&2\end{bmatrix}$ and say whether $A$ is invertible.

#### Solution
The determinant tells us whether a square matrix has an inverse. A square matrix is invertible exactly when its determinant is nonzero.

*Example*: A $2\times2$ matrix $\begin{bmatrix}a&b\\c&d\end{bmatrix}$ has determinant $ad-bc$.

Expand along the first row of $A$. The cofactor signs in that row are $+,-,+$.

$$
\begin{aligned}
\det(A)
&=2\begin{vmatrix}3&1\\1&2\end{vmatrix}
-1\begin{vmatrix}1&1\\0&2\end{vmatrix}
+0\begin{vmatrix}1&3\\0&1\end{vmatrix}\\
&=2(3\cdot2-1\cdot1)-(1\cdot2-1\cdot0)+0\\
&=2(6-1)-2\\
&=8
\end{aligned}
$$

Since $\det(A)=8\ne0$, the matrix is invertible.

#### Solution
**Final Answer**:
$\det(A)=8$. Since the determinant is nonzero, $A$ is invertible. ^det-invertible

### Exercise 2 (8 pts)
**Original question:** Find eigenvalues and eigenvectors of $B=\begin{bmatrix}4&1\\2&3\end{bmatrix}$. Is $B$ diagonalizable? Justify.

#### Solution
An **eigenvector** is a nonzero vector $v$ for which applying a matrix only scales the vector: $Bv=\lambda v$. The scalar $\lambda$ is the **eigenvalue**.

*Example*: If $Bv=2v$, then $v$ is an eigenvector with eigenvalue $2$.

Eigenvalues satisfy the characteristic equation $\det(B-\lambda I)=0$, where $I$ is the identity matrix.

$$
\begin{aligned}
\det(B-\lambda I)
&=\begin{vmatrix}4-\lambda&1\\2&3-\lambda\end{vmatrix}\\
&=(4-\lambda)(3-\lambda)-2\\
&=\lambda^2-7\lambda+10\\
&=(\lambda-5)(\lambda-2)
\end{aligned}
$$

Thus the eigenvalues are $\lambda=5$ and $\lambda=2$.

For $\lambda=5$, solve $(B-5I)v=0$:
$$
\begin{bmatrix}-1&1\\2&-2\end{bmatrix}
\begin{bmatrix}x\\y\end{bmatrix}
=\begin{bmatrix}0\\0\end{bmatrix}
$$
The first row gives $-x+y=0$, so $y=x$. An eigenvector is $\begin{bmatrix}1\\1\end{bmatrix}$, and its eigenspace is its span.

For $\lambda=2$, solve $(B-2I)v=0$:
$$
\begin{bmatrix}2&1\\2&1\end{bmatrix}
\begin{bmatrix}x\\y\end{bmatrix}
=\begin{bmatrix}0\\0\end{bmatrix}
$$
The row equation is $2x+y=0$, so $y=-2x$. An eigenvector is $\begin{bmatrix}1\\-2\end{bmatrix}$, and its eigenspace is its span.

A $2\times2$ matrix with two distinct eigenvalues has two linearly independent eigenvectors, so it is diagonalizable.

#### Solution
**Final Answer**:
The eigenvalues are $5$ and $2$, with eigenspaces $\operatorname{span}\{(1,1)\}$ and $\operatorname{span}\{(1,-2)\}$, respectively. Since the eigenvalues are distinct, the eigenvectors are linearly independent, so $B$ is diagonalizable. ^B-diagonalizable

### Exercise 3 (8 pts)
**Original question:** Let $W=\operatorname{span}\{(1,1,0),(0,1,1)\}$. Find an orthonormal basis of $W$ with Gram-Schmidt and the orthogonal projection of $v=(1,2,3)$ onto $W$.

#### Solution
An **orthonormal basis** is a basis whose vectors have length $1$ and are perpendicular to each other. **Gram-Schmidt** turns an independent list into an orthogonal list with the same span, then normalizes each vector.

*Example*: If $u_1=(1,0)$ and $u_2=(1,1)$, Gram-Schmidt produces perpendicular vectors spanning the same plane.

Let $a_1=(1,1,0)$ and $a_2=(0,1,1)$. Set $u_1=a_1$. Remove from $a_2$ its component in the direction of $u_1$:
$$
\begin{aligned}
u_2
&=a_2-\frac{a_2\cdot u_1}{u_1\cdot u_1}u_1\\
&=(0,1,1)-\frac{1}{2}(1,1,0)\\
&=\left(-\frac12,\frac12,1\right)
\end{aligned}
$$

Normalize the first vector:
$$
e_1=\frac{u_1}{\|u_1\|}=\frac{1}{\sqrt2}(1,1,0)
$$

The second vector has squared length
$$
\|u_2\|^2=\frac14+\frac14+1=\frac32.
$$
Therefore
$$
e_2=\frac{u_2}{\|u_2\|}
=\frac{1}{\sqrt6}(-1,1,2).
$$

The orthogonal projection onto a subspace with orthonormal basis $\{e_1,e_2\}$ is the sum of the components along those basis vectors:
$$
\operatorname{proj}_W(v)=(v\cdot e_1)e_1+(v\cdot e_2)e_2.
$$

Compute the coefficients:
$$
v\cdot e_1=\frac{3}{\sqrt2},\qquad
v\cdot e_2=\frac{7}{\sqrt6}.
$$
Then
$$
\begin{aligned}
\operatorname{proj}_W(v)
&=\frac{3}{\sqrt2}\frac{1}{\sqrt2}(1,1,0)
+\frac{7}{\sqrt6}\frac{1}{\sqrt6}(-1,1,2)\\
&=\left(\frac32,\frac32,0\right)
+\left(-\frac76,\frac76,\frac73\right)\\
&=\left(\frac13,\frac83,\frac73\right).
\end{aligned}
$$

#### Solution
**Final Answer**:
An orthonormal basis is
$$
\left\{\frac{1}{\sqrt2}(1,1,0),\frac{1}{\sqrt6}(-1,1,2)\right\}.
$$
The projection is $\operatorname{proj}_W(v)=\left(\frac13,\frac83,\frac73\right)$. ^gram-projection

### Exercise 4 (8 pts)
**Original question:** For which values of $k$ does the system $x+y+kz=1$, $x+ky+z=1$, $kx+y+z=1$ have unique, infinite or no solutions?

#### Solution
A square linear system has a unique solution when its coefficient matrix has nonzero determinant. When the determinant is zero, the system may have infinitely many solutions or no solutions; row reduction distinguishes those cases.

*Example*: For a coefficient matrix $K$, $\det(K)\ne0$ means exactly one solution for every right-hand side.

The coefficient matrix is
$$
K=\begin{bmatrix}1&1&k\\1&k&1\\k&1&1\end{bmatrix}.
$$

Subtract the first equation from the second and third:
$$
(k-1)(y-z)=0,\qquad (k-1)(x-z)=0.
$$

If $k\ne1$, these imply $x=y=z$. Substitution into any equation gives $(k+2)x=1$.

If also $k\ne-2$, there is a unique solution $x=y=z=\frac{1}{k+2}$.

If $k=-2$, the equations require $x=y=z$ and $0=1$, so there is no solution.

If $k=1$, all three equations reduce to $x+y+z=1$, which has infinitely many solutions.

#### Solution
**Final Answer**:
The system has a unique solution when $k\ne1$ and $k\ne-2$. It has infinitely many solutions when $k=1$. It has no solution when $k=-2$. ^k-system

## 10 February 2026 Exam
### Exercise 1 (5 pts)
**Original question:** State the rank-nullity theorem and apply it to $f:\mathbb{R}^4\to\mathbb{R}^3$, $f(x)=Mx$ with $M$ given.

#### Solution
The **rank** of a linear map is the dimension of its image. The **nullity** is the dimension of its kernel. The rank-nullity theorem says that the dimension of the domain equals rank plus nullity.

*Example*: If a map from $\mathbb{R}^4$ has rank $3$, its nullity is $4-3=1$.

For $f:\mathbb{R}^4\to\mathbb{R}^3$, the domain has dimension $4$. Thus
$$
\dim(\ker f)+\dim(\operatorname{im} f)=4.
$$

The matrix $M$ is not present in the supplied exam text, so its rank cannot be computed. The theorem still gives the relationship between the dimensions.

#### Solution
**Final Answer**:
For a linear map $f:V\to W$ with finite-dimensional domain, $\dim(V)=\operatorname{rank}(f)+\operatorname{nullity}(f)$. Here, $\dim(\ker f)+\dim(\operatorname{im} f)=4$. The numerical rank and nullity cannot be determined without the entries of $M$. ^rank-nullity

### Exercise 2 (9 pts)
**Original question:** Diagonalize $C=\begin{bmatrix}1&2&0\\2&1&0\\0&0&3\end{bmatrix}$ with an orthogonal matrix.

#### Solution
An **orthogonal diagonalization** writes a symmetric matrix as $C=QDQ^T$, where the columns of $Q$ are orthonormal eigenvectors and $D$ contains their eigenvalues in the same order.

*Example*: If the columns of $Q$ are unit eigenvectors, then $Q^TQ=I$.

The matrix is symmetric. Its upper-left block $\begin{bmatrix}1&2\\2&1\end{bmatrix}$ has eigenvectors $(1,1)$ and $(1,-1)$, with eigenvalues $3$ and $-1$. The third coordinate vector $(0,0,1)$ has eigenvalue $3$.

Normalize the vectors:
$$
q_1=\frac{1}{\sqrt2}(1,1,0),\quad
q_2=(0,0,1),\quad
q_3=\frac{1}{\sqrt2}(1,-1,0).
$$

These vectors are orthonormal. Place them as columns of $Q$ in the same order as the eigenvalues:
$$
Q=\begin{bmatrix}
\frac{1}{\sqrt2}&0&\frac{1}{\sqrt2}\\
\frac{1}{\sqrt2}&0&-\frac{1}{\sqrt2}\\
0&1&0
\end{bmatrix},
\qquad
D=\begin{bmatrix}3&0&0\\0&3&0\\0&0&-1\end{bmatrix}.
$$

Then $C=QDQ^T$.

#### Solution
**Final Answer**:
One orthogonal diagonalization is $C=QDQ^T$, where
$$
Q=\begin{bmatrix}
\frac{1}{\sqrt2}&0&\frac{1}{\sqrt2}\\
\frac{1}{\sqrt2}&0&-\frac{1}{\sqrt2}\\
0&1&0
\end{bmatrix},
\qquad
D=\begin{bmatrix}3&0&0\\0&3&0\\0&0&-1\end{bmatrix}.
$$
^orthogonal-diagonalization

### Exercise 3 (8 pts)
**Original question:** Find the kernel and image of the linear map $g(x,y,z)=(x+y,y+z,x-z)$.

#### Solution
The **kernel** is the set of inputs mapped to zero. The **image** is the set of all outputs the map can produce.

*Example*: To find the kernel, set all output coordinates equal to zero and solve the resulting equations.

The matrix of $g$ is
$$
G=\begin{bmatrix}1&1&0\\0&1&1\\1&0&-1\end{bmatrix}.
$$

For the kernel, solve
$$
x+y=0,\qquad y+z=0,\qquad x-z=0.
$$
The first two equations give $y=-x$ and $z=x$. The third then holds. Hence
$$
\ker(g)=\{t(1,-1,1):t\in\mathbb{R}\}.
$$

The image is the column space of $G$. Its columns are $(1,0,1)$, $(1,1,0)$ and $(0,1,-1)$. The third column equals the first minus the second, so the first two columns span the image. They are linearly independent. Therefore
$$
\operatorname{im}(g)=\operatorname{span}\{(1,0,1),(1,1,0)\}.
$$

#### Solution
**Final Answer**:
$$
\ker(g)=\operatorname{span}\{(1,-1,1)\},\qquad
\operatorname{im}(g)=\operatorname{span}\{(1,0,1),(1,1,0)\}.
$$
^kernel-image

### Exercise 4 (8 pts)
**Original question:** Prove that eigenvectors associated with distinct eigenvalues are linearly independent.

#### Solution
An eigenvector of a matrix $A$ is a nonzero vector $v$ satisfying $Av=\lambda v$ for some scalar $\lambda$. The corresponding scalar $\lambda$ is its eigenvalue.

*Example*: If $Av_1=\lambda_1v_1$ and $Av_2=\lambda_2v_2$, with $\lambda_1\ne\lambda_2$, then the two eigenvectors point in independent directions.

We prove the claim by induction on the number $m$ of eigenvectors. For $m=1$, a single eigenvector is nonzero, so it is linearly independent.

Assume the result holds for $m-1$ eigenvectors with distinct eigenvalues. Let $v_1,\ldots,v_m$ have distinct eigenvalues $\lambda_1,\ldots,\lambda_m$. Suppose
$$
c_1v_1+\cdots+c_mv_m=0.
$$

Apply $A$ to both sides:
$$
c_1\lambda_1v_1+\cdots+c_m\lambda_mv_m=0.
$$

Subtract $\lambda_m$ times the original equation:
$$
c_1(\lambda_1-\lambda_m)v_1+\cdots+c_{m-1}(\lambda_{m-1}-\lambda_m)v_{m-1}=0.
$$

The first $m-1$ eigenvalues are distinct, so by the induction hypothesis their eigenvectors are linearly independent. Therefore each coefficient $c_i(\lambda_i-\lambda_m)$ is zero for $i<m$. Since $\lambda_i\ne\lambda_m$, each $c_i=0$ for $i<m$. The original equation then gives $c_m v_m=0$, and because $v_m\ne0$, $c_m=0$. Thus all coefficients are zero.

#### Solution
**Final Answer**:
Let $v_1,\ldots,v_m$ be eigenvectors of $A$ with distinct eigenvalues $\lambda_1,\ldots,\lambda_m$. Suppose $\sum_{i=1}^m c_iv_i=0$. Applying $A$ and subtracting $\lambda_m$ times the original relation gives $\sum_{i=1}^{m-1}c_i(\lambda_i-\lambda_m)v_i=0$. By induction, $v_1,\ldots,v_{m-1}$ are linearly independent. Since $\lambda_i-\lambda_m\ne0$, $c_i=0$ for $i<m$, and then the original relation gives $c_m=0$. Therefore all the eigenvectors are linearly independent. ^independent-eigenvectors
FILE>>
