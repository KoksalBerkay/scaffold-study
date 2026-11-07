---
tags:
  - physics-ii
status: growing
---
# Gauss's Law - Foundations
This note introduces electric flux and Gauss's law through the field of a conducting sphere. Later additions can cover more charge distributions and applications.

Related practice: [[Past Exams#Exercise Problem 1|Conducting sphere]]

## Electric flux
**Electric flux** measures how much electric field passes through a surface. For a small area element $d\mathbf{A}$, the vector is perpendicular to the surface.

*Example:* A uniform field perpendicular to a flat area $A$ has flux $\Phi_E=EA$.

$$
\Phi_E = \int \mathbf{E}\cdot d\mathbf{A}
$$

For a closed surface, the integral is written with a loop on the integral sign:

$$
\oint \mathbf{E}\cdot d\mathbf{A}
$$

## Gauss's law
**Gauss's law** says that the total electric flux through a closed surface depends only on the charge enclosed by that surface.

*Example:* A spherical surface enclosing charge $Q$ has total flux $Q/\varepsilon_0$.

$$
\oint \mathbf{E}\cdot d\mathbf{A} = \frac{Q_{\text{enc}}}{\varepsilon_0}
$$

Here, $Q_{\text{enc}}$ means enclosed charge and $\varepsilon_0$ is the permittivity of free space. Gauss's law is always true, but it is easiest to use to find $\mathbf{E}$ when the charge distribution has strong symmetry.

> [!important] Enclosed charge and field
> Gauss's law relates the flux to enclosed charge. Charges outside the surface may affect the field at points on it, but do not change the net flux through the closed surface.

## Symmetry and Gaussian surfaces
A **Gaussian surface** is an imaginary closed surface chosen to match the symmetry of a charge distribution. Spherical symmetry suggests a sphere; cylindrical symmetry suggests a cylinder; planar symmetry suggests a pillbox.

For a conducting sphere in electrostatic equilibrium, the field inside the conducting material is zero. Outside, spherical symmetry makes the field radial and constant in magnitude over a concentric sphere. For $r>R$:

$$
E(4\pi r^2)=\frac{Q}{\varepsilon_0}
$$

Solving gives

$$
\mathbf{E}(r)=\frac{Q}{4\pi\varepsilon_0r^2}\hat{\mathbf{r}}
$$

For $r<R$, the field in the conducting material is zero.

## Electric potential
**Electric potential** is electric potential energy per unit charge. A zero electric field means potential is constant in that region because potential changes only when there is a field along the path.

*Example:* Inside the charged conducting sphere, $V$ is constant and equals the surface potential when $V(\infty)=0$.

For the conducting sphere of radius $R$ and charge $Q$:

$$
V(r)=
\begin{cases}
\frac{Q}{4\pi\varepsilon_0R}, & r\le R \\
\frac{Q}{4\pi\varepsilon_0r}, & r\ge R
\end{cases}
$$
FILE>>
