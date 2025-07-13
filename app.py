from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import create_engine, text
import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os


app = Flask(__name__)
app.secret_key = '4096'

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

DATABASE_URL = os.getenv("DATABASE_URL")  # this should be set in Render's environment tab
engine = create_engine(DATABASE_URL)

df = pd.read_csv("ski_info.csv")

# Column metadata
ALL_COLUMNS = {
    "state": "State",
    "vertical_drop": "Vertical Drop (feet)",
    "base_elevation": "Base Elevation (feet)",
    "peak_elevation": "Peak Elevation (feet)",
    "slope_length": "Slope Length (miles)",
    "acreage": "Acreage (acres)",
    "snowfall": "Annual Snowfall (inches)",
    "owner": "Owner",
    "lift_total": "Total Lift Count",
    "price": "Day Ticket Price"
}

FILTER_LABELS = {
    "state": "State",
    "vertical_drop": "Vertical Drop",
    "base_elevation": "Base Elevation",
    "peak_elevation": "Peak Elevation",
    "slope_length": "Slope Length",
    "acreage": "Acreage",
    "snowfall": "Annual Snowfall",
    "owner": "Owner",
    "lift_total": "Total Lift Count",
    "price": "Day Ticket Price"
}
        
@app.context_processor
def inject_resort_names():
    resort_names = df['name'].sort_values().unique().tolist()
    return dict(resort_names=resort_names)

@app.route('/')
def home():
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO visit_stats (ip_address, user_agent) VALUES (:ip, :ua)"),
            {"ip": ip, "ua": user_agent}
        )
    return redirect(url_for('index', columns=['state', 'vertical_drop', 'snowfall', 'price']))
    
@app.route('/index')
def index():

    resort_names = df['name'].sort_values().unique().tolist()
    # Default visible columns
    default_columns = ["state", "vertical_drop", "snowfall", "price"]

    # Check if 'columns' is in the request arguments
    if not request.args:
        selected_columns = default_columns
    else:
        selected_columns = request.args.getlist("columns")  # could be empty, and that’s okay

    # Sort options
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('sort_order', 'asc')

    if sort_by not in ['name'] + list(ALL_COLUMNS.keys()):
        sort_by = 'name'
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'
    
    if sort_by not in selected_columns and sort_by != 'name':
        selected_columns.append(sort_by)

    nonprofit_only = request.args.get("nonprofit") == "yes"
    surface_lifts_only = request.args.get("surface_lifts_only") == "yes"

    # Pagination (only apply if nonprofit filter not selected)
    if not nonprofit_only and not surface_lifts_only:
        page = int(request.args.get('page', 1))
        per_page = 100
        offset = (page - 1) * per_page
        limit_offset_clause = "LIMIT :limit OFFSET :offset"
    else:
        page = 1
        per_page = None
        offset = None
        limit_offset_clause = ""

    columns_sql = ', '.join(['name'] + selected_columns)

    if nonprofit_only and surface_lifts_only:
        where_clause = "WHERE nonprofit = 'Yes' AND surface_lifts_only = 'Yes'"
    elif nonprofit_only:
        where_clause = "WHERE nonprofit = 'Yes'"
    elif surface_lifts_only:
        where_clause = "WHERE surface_lifts_only = 'Yes'"
    else:
        where_clause = ""

    query = text(f"""
        SELECT {columns_sql}
        FROM resorts
        {where_clause}
        ORDER BY {sort_by} {sort_order}
        {limit_offset_clause}
    """)

    params = {"limit": per_page, "offset": offset} if not nonprofit_only and not surface_lifts_only else {}

    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()


    return render_template(
        'index.html',
        resorts=result,
        page=page,
        columns=selected_columns,
        column_labels={k: v for k, v in ALL_COLUMNS.items() if k in selected_columns},
        filter_labels=FILTER_LABELS,
        all_columns=ALL_COLUMNS,
        sort_by=sort_by,
        sort_order=sort_order,
        nonprofit=nonprofit_only,
        surface_lifts_only=surface_lifts_only,
        resort_names=resort_names
    )

@app.route('/map')
def map_view():
    return render_template('map_view.html')


# Create Dash app inside Flask
dash_app = dash.Dash(
    __name__,
    server=app,
    url_base_pathname='/map/',  # Dash app will be served at /map
    external_stylesheets=[
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'
    ]
)

owners = sorted(df['owner'].dropna().unique())
lift_options = sorted(df['surface_lifts_only'].dropna().unique())
sort_vars = ['vertical_drop_ft', 'base_elevation_ft', 'peak_elevation_ft', 'price', 'total_lifts']
sort_dict = {
    'Vertical Drop': 'vertical_drop_ft',
    'Base Elevation': 'base_elevation_ft',
    'Peak Elevation': 'peak_elevation_ft',
    'Day Ticket Price': 'price',
    #'Annual Snowfall': 'annual_snowfall',
    #'Slope Length': 'slope_mi',
    #'Acreage': 'skiable_acres',
    'Total Lifts': 'total_lifts'
}

lift_label_map = {
    'Yes': 'No aerial lifts',
    'No': 'Has aerial lifts'
}
lift_options_remapped = [{'label': lift_label_map[o], 'value': o} for o in lift_options]

dash_app.layout = html.Div(style={
    'fontFamily': "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    'margin': '0',
    'padding': '0',
    'backgroundColor': '#fafafa',
    'lineHeight': '1'  # Add this line
}, children=[

    
    
    # Map container with better styling
    html.Div(style={
        'position': 'relative',
        'width': '98vw',
        'height': '90vh',
        'minHeight': '500px',
        'margin': '0 auto',
        'backgroundColor': 'white',
        'borderRadius': '12px',
        'boxShadow': '0 4px 12px rgba(0, 0, 0, 0.1)',
        'overflow': 'hidden'
    }, children=[

        dcc.Graph(
                id='ski-map',
                style={'position': 'absolute', 'top': 0, 'left': 0, 'width': '100%', 'height': '100%'},
                config={
                    'scrollZoom': True,
                    'displayModeBar': False,
                    'doubleClick': 'reset'
                }
        ),

        html.Div(
            id="map-spinner",
            style={
                'position': 'absolute',
                'top': '0',
                'left': '0',
                'width': '100%',
                'height': '100%',
                'backgroundColor': 'rgba(255, 255, 255, 0.9)',
                'display': 'flex',
                'justifyContent': 'center',
                'alignItems': 'center',
                'zIndex': 20  # above the map but below the filter panel
            },
            children=html.Div(className='spinner')
        ),



        # Enhanced Filter Panel
        html.Div(className='filter-panel', style={
            'position': 'absolute',
            'top': '20px',
            'right': '20px',
            'backgroundColor': 'rgba(255, 255, 255, 0.95)',
            'backdropFilter': 'blur(10px)',
            'border': '1px solid rgba(255, 255, 255, 0.3)',
            'borderRadius': '12px',
            'padding': '20px',
            'boxShadow': '0 8px 32px rgba(0, 0, 0, 0.15)',
            'zIndex': 10,
            'width': '280px',
            'minHeight': '200px',
            'maxHeight': '80vh',
        }, children=[
            html.H3("Sort", style={
                'margin': '0 0 16px 0',
                'fontSize': '18px',
                'fontWeight': '600',
                'color': '#111'
            }),

            html.Div(style={'marginBottom': '20px'}, children=[
                html.Label("Color & Size By", style={
                    'fontSize': '14px',
                    'fontWeight': '500',
                    'color': '#555',
                    'marginBottom': '8px',
                    'display': 'block'
                }),
                dcc.Dropdown(
                    id='sort-variable',
                    options=[{'label': label, 'value': key} for label, key in sort_dict.items()],
                    value=None,
                    style={'fontSize': '14px',
                            'position': 'relative'},
                    maxHeight=400
                ),
            ]),

            html.H3("Filters", style={
                'margin': '0 0 16px 0',
                'fontSize': '18px',
                'fontWeight': '600',
                'color': '#111'
            }),
            
            html.Div(style={'marginBottom': '20px'}, children=[
                html.Label("Resort Owner", style={
                    'fontSize': '14px',
                    'fontWeight': '500',
                    'color': '#555',
                    'marginBottom': '8px',
                    'display': 'block'
                }),
                dcc.Dropdown(
                    id='owner-filter',
                    options=[{'label': o, 'value': o} for o in owners],
                    value=owners,
                    multi=True,
                    placeholder='Select owners...',
                    style={'fontSize': '14px'},
                    maxHeight=200
                )
            ]),
            
            
            html.Div(style={'marginBottom': '20px'}, children=[
                html.Label("Surface Lifts Only", style={
                    'fontSize': '14px',
                    'fontWeight': '500',
                    'color': '#555',
                    'marginBottom': '8px',
                    'display': 'block'
                }),
                dcc.Dropdown(
                    id='lift-filter',
                    options=lift_options_remapped,
                    value=None,
                    placeholder='All lift types',
                    style={'fontSize': '14px',
                           'overflow': 'visible'
                           }
                )
            ]),

            html.Div(style={'marginBottom': '20px'}, children=[
                html.Label("Non-profit Resorts Only", style={
                    'fontSize': '14px',
                    'fontWeight': '500',
                    'color': '#555',
                    'marginBottom': '8px',
                    'display': 'block'
                }),
                html.Div(id='nonprofit-checkbox-container', style={
                    'display': 'flex',
                    'alignItems': 'center',
                    'gap': '8px',
                    'padding': '8px',
                    'border': '1px solid #ccc',
                    'borderRadius': '6px',
                    'backgroundColor': 'white',
                    'cursor': 'pointer'
                }, children=[
                    html.Div(id='nonprofit-checkbox', style={
                        'width': '16px',
                        'height': '16px',
                        'border': '2px solid #8396ff',
                        'borderRadius': '3px',
                        'backgroundColor': 'white',
                        'display': 'flex',
                        'alignItems': 'center',
                        'justifyContent': 'center'
                    }),
                    html.Label("Show only non-profit resorts", style={
                        'fontSize': '14px',
                        'color': '#555',
                        'margin': '0',
                        'cursor': 'pointer'
                    })
                ]),
                dcc.Store(id='nonprofit-checkbox-state', data=False)
            ])
            
        ]),

        html.Div(
            id='resort-count',
            style={
                'position': 'absolute',
                'top': '20px',
                'left': '20px',
                'backgroundColor': 'rgba(255, 255, 255, 0.9)',
                'backdropFilter': 'blur(10px)',
                'padding': '8px 12px',
                'borderRadius': '6px',
                'fontSize': '12px',
                'color': '#666',
                'zIndex': 10
            },
            children="Showing 0 ski resorts"
        ),

        html.Div(
            id='resort-popup',
            style={
                'display': 'none',
                'position': 'absolute',
                'zIndex': 30,
                'backgroundColor': 'white',
                'border': '1px solid #ccc',
                'padding': '10px 15px',
                'borderRadius': '8px',
                'boxShadow': '0 4px 12px rgba(0,0,0,0.1)',
                'transform': 'translate(-50%, -100%)',
                'pointerEvents': 'none'  # avoids interfering with map
            }
        )


    
    ])
    
])


@dash_app.callback(
    Output('resort-popup', 'style'),
    Output('resort-popup', 'children'),
    Output('popup-visible', 'data'),
    Input('ski-map', 'clickData'),
    State('sort-variable', 'value')
)
def show_popup(click_data, sort_var):
    if not click_data or not click_data['points']:
        return {'display': 'none'}, "", False

    point = click_data['points'][0]
    resort_name = point['customdata'][0]

    resort_info = df[df['name'] == resort_name].iloc[0]
    
    state = resort_info['state']
    owner = resort_info['owner'] or "N/A"
    sort_val = resort_info.get(sort_var, "N/A")
    sort_label = sort_dict.get(sort_var, sort_var.replace('_', ' ').title())

    link_name = resort_name.replace(" ", "%20")
    
    content = html.Div([
        html.A(resort_name, href=f"/resort/{link_name}", style={
            'fontWeight': '600',
            'color': '#1a73e8',
            'textDecoration': 'none',
            'fontSize': '16px',
            'display': 'block',
            'marginBottom': '6px'
        }),
        html.Div(f"State: {state}", style={'fontSize': '14px'}),
        html.Div(f"Owner: {owner}", style={'fontSize': '14px'}),
        html.Div(f"{sort_label}: {sort_val}", style={'fontSize': '14px'})
    ])

    pixel_x = point.get('x', 0)
    pixel_y = point.get('y', 0)

    style = {
        'display': 'block',
        'left': f"{pixel_x}px",
        'top': f"{pixel_y}px",
        'position': 'absolute',
        'zIndex': 30,
        'backgroundColor': 'white',
        'border': '1px solid #ccc',
        'padding': '10px 15px',
        'borderRadius': '8px',
        'boxShadow': '0 4px 12px rgba(0,0,0,0.1)',
        'transform': 'translate(-50%, -100%)',
        'pointerEvents': 'none'
    }

    return style, content, True




@dash_app.callback(
    Output("map-spinner", "style"),
    Input("ski-map", "figure")
)
def hide_spinner(_):
    return {
        'display': 'none'
    }



@dash_app.callback(
    Output('ski-map', 'figure'),
    Input('owner-filter', 'value'),
    Input('lift-filter', 'value'),
    Input('sort-variable', 'value'),
    Input('nonprofit-checkbox-state', 'data')
)
def update_map(owner, lift, sort_var, nonprofit_checked):
    column_lookup = {
        'vertical_drop_ft': 'Vertical Drop (ft)',
        'base_elevation_ft': 'Base Elevation (ft)',
        'peak_elevation_ft': 'Peak Elevation (ft)',
        'price': 'Day Ticket Price ($)',
        'annual_snowfall': 'Annual Snowfall (in)',
        'slope_mi': 'Slope Length (mi)',
        'skiable_acres': 'Skiable Acres',
        'total_lifts': 'Total Lifts'
    }
    sort_label = column_lookup.get(sort_var, 'price')
    filtered_df = df.copy()
    if owner:
        filtered_df = filtered_df[filtered_df['owner'].isin(owner)]

    if lift:
        filtered_df = filtered_df[filtered_df['surface_lifts_only'] == lift]

    if nonprofit_checked:
        filtered_df = filtered_df[filtered_df['nonprofit'] == 'Yes']


    # Create custom hover text
    filtered_df['hover_text'] = ('<br>' +
        '<b>' + filtered_df['name'] + '</b><br>' +
        filtered_df['state'] + '<br>' + '<br>'
        '<span style="color: #7f8c8d;">Owner:</span> ' + filtered_df['owner'].fillna('N/A') + '<br>' +
        '<span style="color: #7f8c8d;">Day Ticket:</span> $' + filtered_df['price'].astype(str) + '<br>' +
        '<span style="color: #7f8c8d;">Vertical Drop:</span> ' + filtered_df['vertical_drop_ft'].astype(str) + ' ft<br>' +
        '<span style="color: #7f8c8d;">Annual Snowfall:</span> ' + filtered_df['annual_snowfall'].astype(str) + '"<br>' +
        '<span style="color: #7f8c8d;">Skiable Acres:</span> ' + filtered_df['skiable_acres'].astype(str) + ' ac' + '<br>' +
        '<span style="color: #7f8c8d;">Total Lifts:</span> ' + filtered_df['total_lifts'].astype(str) + '<br>'
    )

    if sort_var:
        fig = px.scatter_mapbox(
            filtered_df,
            lat='latitude',
            lon='longitude',
            hover_name=None,
            custom_data=['name'],
            hover_data={
                'name': True,
                'owner': True,
                'state': False,
                sort_var: True if sort_var else False,
                'latitude': False,
                'longitude': False
            },

            color=sort_var,
            size=sort_var,
            size_max=15,
            color_continuous_scale='Viridis',
            zoom=3,
            height=None,
            title=""
        )

    else:
        fig = px.scatter_mapbox(
            filtered_df,
            lat='latitude',
            lon='longitude',
            hover_name='name',
            hover_data={
                'state': True,
                'owner': True,
                'latitude': False,
                'longitude': False
            },
            zoom=3,
            height=None,
            title=""
        )

        # Manually set a uniform color
        fig.update_traces(marker=dict(color='#607695', size=6, opacity=0.8))

    # Update hover template to use custom hover text
    fig.update_traces(
        hovertemplate='%{text}<extra></extra>',
        text=filtered_df['hover_text']
    )

    fig.update_layout(
        mapbox=dict(
            style='carto-positron',
            center=dict(lat=45, lon=-100),
            zoom=3
        ),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
            size=12,
            color="#111"
        ),
        # Style the hover labels to match your website
        hoverlabel=dict(
            bgcolor="#f8f9fa",
            bordercolor="#eee",
            font=dict(
                size=14,
                family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
                color="#1a1a1a",
            ),
            namelength=-1,
            align="left"
        ),
        coloraxis=dict(
            colorbar=dict(
                title=dict(text=sort_label, font=dict(size=12)),
                len=0.6,
                thickness=15,
                bgcolor='rgba(255,255,255,0.9)',
                x=0.02,
                y=0.02,
                xanchor='left',
                yanchor='bottom',
                outlinewidth=1,
                outlinecolor='rgba(0,0,0,0.1)',
                borderwidth=1,
                bordercolor='rgba(0,0,0,0.1)'
            )
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    

    return fig
    

@dash_app.callback(
    Output('resort-count', 'children'),
    Input('owner-filter', 'value'),
    Input('lift-filter', 'value'),
    Input('nonprofit-checkbox-state', 'data')
)
def update_resort_count(owner, lift, nonprofit_checked):
    filtered_df = df.copy()
    if owner:
        filtered_df = filtered_df[filtered_df['owner'].isin(owner)]
    if lift:
        filtered_df = filtered_df[filtered_df['surface_lifts_only'] == lift]
    if nonprofit_checked:
        filtered_df = filtered_df[filtered_df['nonprofit'] == 'Yes']
    return f"Showing {len(filtered_df)} ski resorts"


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/thank-you', methods=['POST'])
def submit_feedback():
    email = request.form.get('email') or "Anonymous"
    message = request.form.get('feedback')

    print(f"[FEEDBACK] {email}: {message}")

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO feedback (email, message) VALUES (:email, :message)"),
            {"email": email, "message": message}
        )

    print('INSERT SUCCESSFUL')

    return render_template('submitted_feedback.html')


@dash_app.callback(
    Output('nonprofit-checkbox-state', 'data'),
    Input('nonprofit-checkbox-container', 'n_clicks'),
    State('nonprofit-checkbox-state', 'data'),
    prevent_initial_call=True
)
def toggle_nonprofit_checkbox(n_clicks, current_state):
    return not current_state


@dash_app.callback(
    Output('nonprofit-checkbox', 'style'),
    Input('nonprofit-checkbox-state', 'data')
)
def update_checkbox_style(is_checked):
    base_style = {
        'width': '16px',
        'height': '16px',
        'border': '2px solid #8396ff',
        'borderRadius': '3px',
        'display': 'flex',
        'alignItems': 'center',
        'justifyContent': 'center'
    }
    
    if is_checked:
        base_style.update({
            'backgroundColor': '#8396ff',
            'color': 'white'
        })
        return base_style
    else:
        base_style.update({
            'backgroundColor': 'white'
        })
        return base_style
    
@dash_app.callback(
Output('nonprofit-checkbox', 'children'),
Input('nonprofit-checkbox-state', 'data')
)
def update_checkbox_content(is_checked):
    if is_checked:
        return "✓"
    return ""



@app.route("/resort/<resort_name>")
def resort_page(resort_name):
    df_display = df.copy()
    df_display['annual_snowfall'] = df_display['annual_snowfall'].astype('Int64')
    df_display['price'] = df_display['price'].astype(int)
    df_display['skiable_acres'] = df_display['skiable_acres'].astype('Int64')
    df_display['annual_snowfall'] = df_display['annual_snowfall'].astype(str)
    df_display['price'] = df_display['price'].astype(str)
    df_display['skiable_acres'] = df_display['skiable_acres'].astype(str)
    df_display.replace('<NA>', 'N/A', inplace=True)



    resort = df_display[df_display["name"] == resort_name].to_dict(orient="records")
    resort = resort[0]
    if not resort:
        return "Resort not found", 404
    fig = px.scatter_mapbox(
        lat=[resort['latitude']],
        lon=[resort['longitude']],
        zoom=5,
        height=500,
        hover_name=[resort['name']],  # This will be the main hover text
        hover_data={},  # Empty dict to hide all other hover data
    )

    # Update the marker style to match your page design
    fig.update_traces(
        marker=dict(
            size=10,
            color='#2c3e50',  # Dark blue-gray to match your text color
            symbol='circle',
        ),
        hovertemplate='%{hovertext}<extra></extra>',  # Custom hover template
        hovertext=[resort['name']],  # Only show resort name
    )

    fig.update_layout(
        mapbox_style="carto-positron",
        margin={"r":0,"t":0,"l":0,"b":0},
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#eee",
            font_size=14,
            font_family="Inter, sans-serif",  # Match your page font
            font_color="#1a1a1a",
            font_weight=500
        )
    )

    # Remove Plotly mode bar and set responsive
    config = {"displayModeBar": False,   # hides top menu bar
    "scrollZoom": True,        # allow mouse wheel zoom
    "displaylogo": False,      # hide Plotly logo
    "modeBarButtonsToRemove": ['zoom2d', 'pan2d', 'select2d', 'lasso2d'],  # optional
    "responsive": True}
    map_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn', config=config)

    return render_template("resort.html", resort=resort, map_html=map_html)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').strip().lower()

    if not query:
        flash("Please enter a resort name.")
        return redirect(url_for('index'))

    match = df[df['name'].str.lower() == query]
    if not match.empty:
        resort_name = match.iloc[0]['name']
        return redirect(url_for('resort_detail', resort_name=resort_name))
    else:
        flash("Resort not found.")
        return redirect(url_for('index'))

@app.route('/resort/<resort_name>')
def resort_detail(resort_name):
    resort = df[df['name'] == resort_name]
    if resort.empty:
        return "Resort not found", 404
    return render_template('resort_detail.html', resort=resort.iloc[0])




if __name__ == '__main__':
    app.run(debug=True)
